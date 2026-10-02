import json
import ssl
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse
from ldap3.core.exceptions import LDAPException

from config.auth_backends import ActiveDirectoryBackend, RegisteredUserModelBackend
from estoque.models import Certificacao, Equipamento
from estoque.services.certificate_payloads import parse_certificate_payloads
from historico.models import UserAccess


class CertificatePayloadValidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.valid_item = {
            "nome": "NR-11",
            "empresa": "Certificadora Portuária",
            "codigo": "CERT-001",
            "data": "2026-04-10",
            "vencimento": "2027-04-10",
            "detalhes": "Inspeção anual",
            "notificar": True,
            "email": "seguranca@empresa.com",
        }

    def _request(self, payload, attachment=None):
        data = {"certificados_json": json.dumps(payload)}
        if attachment is not None:
            data["anexo_0"] = attachment
        return self.factory.post("/", data)

    def test_normalizes_valid_payload_and_real_pdf(self):
        attachment = SimpleUploadedFile(
            "certificado.pdf",
            b"%PDF-1.7\nconteudo de teste",
            content_type="application/pdf",
        )

        parsed = parse_certificate_payloads(
            self._request([self.valid_item], attachment)
        )

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["nome_certificado"], "NR-11")
        self.assertEqual(parsed[0]["data_certificacao"], date(2026, 4, 10))
        self.assertEqual(parsed[0]["data_vencimento"], date(2027, 4, 10))
        self.assertTrue(parsed[0]["notificar_por_email"])
        self.assertEqual(parsed[0]["email_notificacao"], "seguranca@empresa.com")
        self.assertEqual(parsed[0]["anexo"].name, "certificado.pdf")
        self.assertEqual(parsed[0]["anexo"].tell(), 0)

    def test_accepts_and_normalizes_multiple_notification_emails(self):
        item = dict(
            self.valid_item,
            email="seguranca@empresa.com, manutencao@empresa.com\nSEGURANCA@empresa.com",
        )

        parsed = parse_certificate_payloads(self._request([item]))

        self.assertEqual(
            parsed[0]["email_notificacao"],
            "seguranca@empresa.com; manutencao@empresa.com",
        )

    def test_rejects_malformed_or_non_list_json(self):
        malformed = self.factory.post("/", {"certificados_json": "{"})
        with self.assertRaisesMessage(
            ValidationError, "dados dos certificados estão inválidos"
        ):
            parse_certificate_payloads(malformed)

        not_a_list = self.factory.post(
            "/", {"certificados_json": json.dumps({"nome": "NR-11"})}
        )
        with self.assertRaisesMessage(
            ValidationError, "lista de certificados está inválida"
        ):
            parse_certificate_payloads(not_a_list)

    def test_rejects_missing_fields_and_more_than_thirty_items(self):
        incomplete = dict(self.valid_item, codigo="")
        with self.assertRaisesMessage(
            ValidationError, "Informe nome, empresa e código"
        ):
            parse_certificate_payloads(self._request([incomplete]))

        with self.assertRaisesMessage(ValidationError, "no máximo 30 certificados"):
            parse_certificate_payloads(self._request([self.valid_item] * 31))

    def test_rejects_invalid_chronology_and_notification_data(self):
        expired_before_issue = dict(self.valid_item, vencimento="2026-04-09")
        with self.assertRaisesMessage(
            ValidationError, "não pode ser anterior à emissão"
        ):
            parse_certificate_payloads(self._request([expired_before_issue]))

        missing_expiry = dict(self.valid_item, vencimento="")
        with self.assertRaisesMessage(ValidationError, "Informe o vencimento"):
            parse_certificate_payloads(self._request([missing_expiry]))

        invalid_email = dict(self.valid_item, email="email-invalido")
        with self.assertRaisesMessage(
            ValidationError, "Os e-mails do certificado 1 são inválidos"
        ):
            parse_certificate_payloads(self._request([invalid_email]))

    def test_rejects_pdf_extension_with_forged_content(self):
        forged = SimpleUploadedFile(
            "certificado.pdf",
            b"isto nao e um pdf",
            content_type="application/pdf",
        )
        with self.assertRaisesMessage(ValidationError, "deve ser um PDF válido"):
            parse_certificate_payloads(self._request([self.valid_item], forged))


@override_settings(LOGIN_FAILURE_LIMIT=3, LOGIN_FAILURE_WINDOW_SECONDS=300)
class LoginHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("operador", password="SenhaCorreta!2026")
        UserAccess.objects.create(user=self.user)

    def tearDown(self):
        cache.clear()

    def test_main_login_blocks_fourth_attempt_even_with_correct_password(self):
        url = reverse("login")
        for _ in range(3):
            response = self.client.post(
                url,
                {"matricula": "operador", "senha": "SenhaErrada!"},
                REMOTE_ADDR="10.0.0.15",
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            url,
            {"matricula": "operador", "senha": "SenhaCorreta!2026"},
            REMOTE_ADDR="10.0.0.15",
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "Muitas tentativas inválidas", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_successful_main_login_clears_previous_failures(self):
        url = reverse("login")
        for _ in range(2):
            self.client.post(
                url,
                {"matricula": "operador", "senha": "SenhaErrada!"},
                REMOTE_ADDR="10.0.0.16",
            )

        success = self.client.post(
            url,
            {"matricula": "operador", "senha": "SenhaCorreta!2026"},
            REMOTE_ADDR="10.0.0.16",
        )
        self.assertRedirects(success, reverse("dashboard"))
        self.client.logout()

        for _ in range(3):
            response = self.client.post(
                url,
                {"matricula": "operador", "senha": "SenhaErrada!"},
                REMOTE_ADDR="10.0.0.16",
            )
            self.assertEqual(response.status_code, 200)

    def test_local_backend_rejects_user_outside_authorized_list(self):
        outsider = User.objects.create_user(
            "fora_da_lista", password="SenhaCorreta!2026"
        )

        authenticated = RegisteredUserModelBackend().authenticate(
            None,
            username=outsider.username,
            password="SenhaCorreta!2026",
        )

        self.assertIsNone(authenticated)

    def test_stock_entry_reuses_main_login_and_returns_to_stock(self):
        stock_entry = reverse("estoque:login")
        stock_dashboard = reverse("estoque:dashboard")
        login_url = reverse("login")

        response = self.client.get(stock_entry)
        self.assertRedirects(
            response,
            f"{login_url}?next={stock_dashboard}",
            fetch_redirect_response=False,
        )
        login_page = self.client.get(response.url)
        self.assertContains(login_page, f'name="next" value="{stock_dashboard}"')

        success = self.client.post(
            login_url,
            {
                "matricula": "operador",
                "senha": "SenhaCorreta!2026",
                "next": stock_dashboard,
            },
            REMOTE_ADDR="10.0.0.17",
        )
        self.assertRedirects(success, stock_dashboard)

    def test_login_rejects_external_next_url(self):
        success = self.client.post(
            reverse("login"),
            {
                "matricula": "operador",
                "senha": "SenhaCorreta!2026",
                "next": "https://malicioso.example/roubo",
            },
            REMOTE_ADDR="10.0.0.19",
        )

        self.assertRedirects(success, reverse("dashboard"))

    @patch("historico.views.login.authenticate")
    def test_unknown_user_is_rejected_without_calling_any_backend(self, authenticate):
        response = self.client.post(
            reverse("login"),
            {"matricula": "nao_cadastrado", "senha": "QualquerSenha!2026"},
            REMOTE_ADDR="10.0.0.21",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login ou senha inválidos")
        authenticate.assert_not_called()


class ProtectedEquipmentMediaTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("dono", password="SenhaForte!2026")
        self.other = User.objects.create_user("outro_media", password="SenhaForte!2026")
        self.manager = User.objects.create_user(
            "gestor_media", password="SenhaForte!2026", is_staff=True
        )
        UserAccess.objects.bulk_create(
            [
                UserAccess(user=self.owner),
                UserAccess(user=self.other),
                UserAccess(user=self.manager),
            ]
        )

    def test_equipment_and_certificate_files_are_shared_with_authenticated_users(self):
        with (
            TemporaryDirectory() as media_root,
            override_settings(MEDIA_ROOT=media_root),
        ):
            photo_path = "equipamentos/1/fotos/equipamento.png"
            qr_path = "equipamentos/1/qrcodes/equipamento.png"
            certificate_path = "equipamentos/1/certificacoes/certificado.pdf"
            for relative, content in (
                (photo_path, b"\x89PNG\r\n\x1a\nfoto"),
                (qr_path, b"\x89PNG\r\n\x1a\nqr"),
                (certificate_path, b"%PDF-1.7\ncertificado"),
            ):
                target = Path(media_root) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

            equipment = Equipamento.objects.create(
                equipamento="Cinta",
                identificador="C-001",
                tipo_equipamento="MANUAL",
                quantidade=1,
                localizacao="Armazém",
                foto=photo_path,
                qrcode=qr_path,
                criado_por=self.owner,
            )
            Certificacao.objects.create(
                equipamento=equipment,
                nome_certificado="NR-11",
                data_certificacao=date(2026, 4, 10),
                data_vencimento=date(2027, 4, 10),
                empresa_certificadora="Certificadora",
                codigo_certificado="CERT-001",
                anexo=certificate_path,
                criado_por=self.owner,
            )

            anonymous_client = Client()
            other_client = Client()
            owner_client = Client()
            manager_client = Client()
            other_client.force_login(self.other)
            owner_client.force_login(self.owner)
            manager_client.force_login(self.manager)
            streaming_responses = []

            for relative in (photo_path, qr_path, certificate_path):
                url = f"/media/{relative}"
                self.assertEqual(anonymous_client.get(url).status_code, 302)
                other_response = other_client.get(url)
                self.assertEqual(other_response.status_code, 200)
                streaming_responses.append(other_response)

                owner_response = owner_client.get(url)
                self.assertEqual(owner_response.status_code, 200)
                self.assertEqual(owner_response["X-Frame-Options"], "SAMEORIGIN")
                streaming_responses.append(owner_response)

                manager_response = manager_client.get(url)
                self.assertEqual(manager_response.status_code, 200)
                streaming_responses.append(manager_response)

            # FileResponse dispara request_finished no close. Em TestCase/MySQL,
            # feche somente depois de concluir todas as consultas desta transação.
            for response in streaming_responses:
                response.close()


class InitialAccessCollisionTests(TestCase):
    def test_existing_non_admin_is_not_silently_promoted(self):
        existing = User.objects.create_user("admin_inicial", password="SenhaComum!2026")

        with self.assertRaisesMessage(
            CommandError, "já existe sem privilégios administrativos"
        ):
            call_command("preparar_acesso_inicial", skip_migrate=True)

        existing.refresh_from_db()
        self.assertFalse(existing.is_staff)
        self.assertFalse(existing.is_superuser)


class LDAPConnectionSecurityTests(SimpleTestCase):
    @override_settings(AD_RECEIVE_TIMEOUT=10)
    @patch("config.auth_backends.Connection")
    def test_starttls_is_completed_before_credentials_are_bound(self, connection_class):
        connection = connection_class.return_value
        connection.start_tls.return_value = True
        connection.bind.return_value = True
        connection.bound = True

        with ActiveDirectoryBackend._connection(
            "server",
            "glibra\\leonardo",
            "senha",
            start_tls=True,
        ):
            pass

        self.assertEqual(
            connection.method_calls,
            [call.open(), call.start_tls(), call.bind(), call.unbind()],
        )

    @override_settings(AD_RECEIVE_TIMEOUT=10)
    @patch("config.auth_backends.Connection")
    def test_failed_bind_never_authenticates(self, connection_class):
        connection = connection_class.return_value
        connection.start_tls.return_value = True
        connection.bind.return_value = False
        connection.bound = False

        with self.assertRaises(LDAPException):
            with ActiveDirectoryBackend._connection(
                "server",
                "glibra\\leonardo",
                "senha-incorreta",
                start_tls=True,
            ):
                pass


class ActiveDirectoryBackendTests(TestCase):
    ad_settings = {
        "AD_AUTH_ENABLED": True,
        "AD_SERVER_URI": "ldap://glibra.corp:389",
        "AD_DIRECT_BIND": True,
        "AD_DOMAIN": "glibra",
        "AD_START_TLS": True,
        "AD_TLS_VALIDATE": True,
        "AD_CA_CERT_FILE": "C:/certificados/glibra-ca.pem",
        "AD_CONNECT_TIMEOUT": 5,
        "AD_RECEIVE_TIMEOUT": 10,
    }

    @override_settings(**ad_settings)
    def test_direct_bind_uses_glibra_account_and_keeps_local_profile(self):
        user = User.objects.create_user(
            "leonardo",
            first_name="Leonardo",
            last_name="Marins",
            password="Temporaria!2026",
        )
        access = UserAccess.objects.create(
            user=user,
            must_change_password=True,
        )
        connection_calls = []

        @contextmanager
        def fake_connection(server, username, password, *, start_tls):
            connection_calls.append((server, username, password, start_tls))
            yield MagicMock()

        backend = ActiveDirectoryBackend()
        tls_token = object()
        server_token = object()
        with (
            patch("config.auth_backends.Tls", return_value=tls_token) as tls_class,
            patch(
                "config.auth_backends.Server", return_value=server_token
            ) as server_class,
            patch.object(backend, "_connection", side_effect=fake_connection),
        ):
            authenticated = backend.authenticate(
                None,
                username="leonardo",
                password="SenhaDoAD!2026",
            )

        self.assertEqual(authenticated.pk, user.pk)
        tls_class.assert_called_once_with(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file="C:/certificados/glibra-ca.pem",
        )
        server_class.assert_called_once()
        _, server_kwargs = server_class.call_args
        self.assertEqual(server_class.call_args.args[0], "glibra.corp")
        self.assertEqual(server_kwargs["port"], 389)
        self.assertFalse(server_kwargs["use_ssl"])
        self.assertIs(server_kwargs["tls"], tls_token)
        self.assertEqual(server_kwargs["connect_timeout"], 5)
        self.assertEqual(
            connection_calls,
            [(server_token, "glibra\\leonardo", "SenhaDoAD!2026", True)],
        )

        user.refresh_from_db()
        access.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "Leonardo")
        self.assertEqual(user.last_name, "Marins")
        self.assertEqual(user.email, "")
        self.assertFalse(access.must_change_password)
        self.assertIsNone(access.temporary_password_created_at)
        self.assertIsNotNone(access.password_changed_at)

    @override_settings(**ad_settings)
    def test_unknown_user_does_not_even_create_ldap_server(self):
        backend = ActiveDirectoryBackend()
        with patch("config.auth_backends.Server") as server_class:
            authenticated = backend.authenticate(
                None,
                username="nao_cadastrado",
                password="SenhaDoAD!2026",
            )

        self.assertIsNone(authenticated)
        server_class.assert_not_called()

    @override_settings(
        AD_AUTH_ENABLED=True,
        AD_SERVER_URI="ldap://glibra.corp:389",
        AD_DIRECT_BIND=True,
        AD_DOMAIN="glibra",
        AD_START_TLS=False,
    )
    def test_unencrypted_ldap_is_refused_before_any_connection(self):
        user = User.objects.create_user("leonardo", password="Temporaria!2026")
        UserAccess.objects.create(user=user)
        backend = ActiveDirectoryBackend()
        with patch("config.auth_backends.Server") as server_class:
            authenticated = backend.authenticate(
                None,
                username="leonardo",
                password="SenhaDoAD!2026",
            )

        self.assertIsNone(authenticated)
        server_class.assert_not_called()
