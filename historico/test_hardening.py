import json
import ssl
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

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

from config.auth_backends import ActiveDirectoryBackend
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
            ValidationError, "e-mail do certificado 1 é inválido"
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


class ProtectedEquipmentMediaTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("dono", password="SenhaForte!2026")
        self.other = User.objects.create_user("outro_media", password="SenhaForte!2026")
        self.manager = User.objects.create_user(
            "gestor_media", password="SenhaForte!2026", is_staff=True
        )

    def test_equipment_and_certificate_files_are_scoped_to_owner_and_manager(self):
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
                self.assertEqual(other_client.get(url).status_code, 404)

                owner_response = owner_client.get(url)
                self.assertEqual(owner_response.status_code, 200)
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


class ActiveDirectoryBackendTests(TestCase):
    ad_settings = {
        "AD_AUTH_ENABLED": True,
        "AD_SERVER_URI": "ldaps://ad.empresa.local:636",
        "AD_BIND_DN": "CN=svc_loggeral,OU=Servicos,DC=empresa,DC=local",
        "AD_BIND_PASSWORD": "senha-servico",
        "AD_USER_SEARCH_BASE": "OU=Usuarios,DC=empresa,DC=local",
        "AD_USER_FILTER": "(sAMAccountName={username})",
        "AD_START_TLS": False,
        "AD_CREATE_USERS": True,
        "AD_ALWAYS_UPDATE_USER": True,
        "AD_TLS_VALIDATE": True,
        "AD_CA_CERT_FILE": "C:/certificados/empresa-ca.pem",
        "AD_CONNECT_TIMEOUT": 5,
        "AD_RECEIVE_TIMEOUT": 10,
    }

    @override_settings(**ad_settings)
    def test_ldaps_validates_certificate_and_clears_temporary_password_state(self):
        user = User.objects.create_user(
            "leonardo", email="antigo@empresa.com", password="Temporaria!2026"
        )
        access = UserAccess.objects.create(
            user=user,
            must_change_password=True,
        )

        entry = MagicMock()
        entry.entry_dn = "CN=Leonardo,OU=Usuarios,DC=empresa,DC=local"
        entry.entry_attributes_as_dict = {
            "sAMAccountName": ["leonardo"],
            "givenName": ["Leonardo"],
            "sn": ["Marins"],
            "mail": ["leonardo@empresa.com"],
        }
        service_connection = MagicMock()
        service_connection.search.return_value = True
        service_connection.entries = [entry]
        user_connection = MagicMock()
        connection_calls = []

        @contextmanager
        def fake_connection(server, username, password, *, start_tls):
            connection_calls.append((server, username, password, start_tls))
            if username == self.ad_settings["AD_BIND_DN"]:
                yield service_connection
            else:
                yield user_connection

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
            ca_certs_file="C:/certificados/empresa-ca.pem",
        )
        server_class.assert_called_once()
        _, server_kwargs = server_class.call_args
        self.assertEqual(server_class.call_args.args[0], "ad.empresa.local")
        self.assertEqual(server_kwargs["port"], 636)
        self.assertTrue(server_kwargs["use_ssl"])
        self.assertIs(server_kwargs["tls"], tls_token)
        self.assertEqual(server_kwargs["connect_timeout"], 5)
        self.assertEqual(len(connection_calls), 2)
        self.assertTrue(all(not item[3] for item in connection_calls))

        user.refresh_from_db()
        access.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "Leonardo")
        self.assertEqual(user.last_name, "Marins")
        self.assertEqual(user.email, "leonardo@empresa.com")
        self.assertFalse(access.must_change_password)
        self.assertIsNone(access.temporary_password_created_at)
        self.assertIsNotNone(access.password_changed_at)

    @override_settings(
        AD_AUTH_ENABLED=True,
        AD_SERVER_URI="ldap://ad.empresa.local:389",
        AD_BIND_DN="CN=svc,DC=empresa,DC=local",
        AD_BIND_PASSWORD="senha-servico",
        AD_USER_SEARCH_BASE="DC=empresa,DC=local",
        AD_START_TLS=False,
    )
    def test_unencrypted_ldap_is_refused_before_any_connection(self):
        backend = ActiveDirectoryBackend()
        with patch("config.auth_backends.Server") as server_class:
            authenticated = backend.authenticate(
                None,
                username="leonardo",
                password="SenhaDoAD!2026",
            )

        self.assertIsNone(authenticated)
        server_class.assert_not_called()
