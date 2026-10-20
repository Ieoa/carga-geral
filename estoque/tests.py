from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from historico.models import AuditLog, UserAccess

from .forms import CertificacaoForm
from .models import Certificacao, Colaborador, Equipamento, MovimentacaoMaterial
from .services.certificacoes import enviar_avisos_certificados


class FakeQrCode:
    def save(self, buffer, format):
        buffer.write(b"fake-png")


class EquipamentoQrCodeTests(TestCase):
    @override_settings(PUBLIC_BASE_URL="https://app.example.com")
    def test_qrcode_uses_public_base_url_when_configured(self):
        with patch(
            "estoque.models.qrcode.make", return_value=FakeQrCode()
        ) as make_qrcode:
            equipamento = Equipamento.objects.create(
                equipamento="Cinta",
                identificador="C-001",
                tipo_equipamento="MANUAL",
                quantidade=1,
                localizacao="Armazem",
            )

        make_qrcode.assert_called_once_with(
            f"https://app.example.com/estoque/qrcode/material/{equipamento.pk}/"
        )

    @override_settings(PUBLIC_BASE_URL="https://app.example.com")
    @patch("estoque.models.qrcode.make", return_value=FakeQrCode())
    def test_command_regenerates_legacy_qrcode_for_pdf_destination(self, make_qrcode):
        equipamento = Equipamento.objects.create(
            equipamento="Manilha",
            identificador="M-001",
            tipo_equipamento="MANUAL",
            quantidade=1,
            localizacao="Armazem",
        )
        Equipamento.objects.filter(pk=equipamento.pk).update(
            qrcode=f"equipamentos/{equipamento.pk}/qrcodes/qrcode_{equipamento.pk}.png"
        )
        make_qrcode.reset_mock()

        output = StringIO()
        call_command("regenerar_qrcodes", stdout=output)

        equipamento.refresh_from_db()
        self.assertIn(f"qrcode_v2_{equipamento.pk}", equipamento.qrcode.name)
        make_qrcode.assert_called_once_with(
            f"https://app.example.com/estoque/qrcode/material/{equipamento.pk}/"
        )
        self.assertIn("1 QR Code(s) regenerado(s)", output.getvalue())


class EquipmentAutocompleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "operador_busca", password="SenhaForte!2026"
        )
        self.other_user = User.objects.create_user(
            "outro_busca", password="SenhaForte!2026"
        )
        UserAccess.objects.create(user=self.user)
        UserAccess.objects.create(user=self.other_user)
        self.client.force_login(self.user)

    def test_rejects_non_ajax_requests_cleanly(self):
        response = self.client.get(reverse("estoque:autocomplete_equipamento"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"erro": "Requisição AJAX obrigatória."})

    @patch("estoque.models.qrcode.make", return_value=FakeQrCode())
    def test_returns_only_distinct_equipment_visible_to_user(self, _make_qrcode):
        for owner, identifier in (
            (self.user, "CIN-001"),
            (self.user, "CIN-002"),
            (self.other_user, "CIN-003"),
        ):
            Equipamento.objects.create(
                equipamento="CINTA",
                identificador=identifier,
                tipo_equipamento="MANUAL",
                quantidade=1,
                localizacao="ARMAZEM",
                criado_por=owner,
            )

        response = self.client.get(
            reverse("estoque:autocomplete_equipamento"),
            {"term": "cin"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["CINTA"])


class EquipmentAndLoanPermissionTests(TestCase):
    def setUp(self):
        self.qr_patcher = patch("estoque.models.qrcode.make", return_value=FakeQrCode())
        self.qr_patcher.start()
        self.owner = User.objects.create_user("dono_material", password="senha")
        self.other = User.objects.create_user("outro_material", password="senha")
        self.manager = User.objects.create_user("gestor_material", password="senha")
        self.admin = User.objects.create_superuser("admin_material", password="senha")
        for user in (self.owner, self.other, self.manager, self.admin):
            UserAccess.objects.create(user=user)
        Colaborador.objects.create(
            user=self.owner, matricula="dono_material", nome="Dono Material", area="MAT", cargo="AUX"
        )
        Colaborador.objects.create(
            user=self.other, matricula="outro_material", nome="Outro Material", area="MAT", cargo="AUX"
        )
        Colaborador.objects.create(
            user=self.manager, matricula="gestor_material", nome="Gestor Material", area="MAT", cargo="SUP"
        )
        self.equipamento = Equipamento.objects.create(
            equipamento="CINTA",
            identificador="CIN-100",
            caracteristica="Poliéster reforçado",
            capacidade_toneladas="5.00",
            tipo_equipamento="MANUAL",
            quantidade=2,
            localizacao="ARMAZEM",
            criado_por=self.owner,
        )

    def tearDown(self):
        self.qr_patcher.stop()

    def equipamento_payload(self, identificador="CIN-100"):
        return {
            "equipamento": "Cinta revisada",
            "identificador": identificador,
            "caracteristica": "Teste",
            "capacidade_toneladas": "5.00",
            "descricao_uso": "Movimentação de carga",
            "tipo_equipamento": "MANUAL",
            "quantidade": 2,
            "localizacao": "Galpão B",
        }

    def criar_equipamento(self, identificador, *, quantidade=5):
        return Equipamento.objects.create(
            equipamento=f"Material {identificador}",
            identificador=identificador,
            tipo_equipamento="MANUAL",
            quantidade=quantidade,
            localizacao="ARMAZEM",
            criado_por=self.owner,
        )

    def lote_payload(self, itens, **cabecalho):
        retirada = timezone.localtime().replace(second=0, microsecond=0)
        payload = {
            "nome": "Maria Operadora",
            "matricula": "MAT-100",
            "empresa_destino": "Empresa Parceira",
            "data_retirada": retirada.strftime("%Y-%m-%dT%H:%M"),
            "data_prevista_devolucao": (retirada + timedelta(days=7)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "itens-TOTAL_FORMS": str(len(itens)),
            "itens-INITIAL_FORMS": "0",
            "itens-MIN_NUM_FORMS": "1",
            "itens-MAX_NUM_FORMS": "50",
        }
        payload.update(cabecalho)
        for indice, (equipamento, quantidade) in enumerate(itens):
            payload[f"itens-{indice}-equipamento"] = equipamento.pk
            payload[f"itens-{indice}-quantidade"] = quantidade
        return payload

    def test_all_users_can_view_but_employee_only_edits_own_material(self):
        other_client = Client()
        other_client.force_login(self.other)
        detail_url = reverse("estoque:detalhe_equipamento", args=[self.equipamento.pk])
        edit_url = reverse("estoque:editar_equipamento", args=[self.equipamento.pk])

        self.assertEqual(other_client.get(detail_url).status_code, 200)
        denied = other_client.post(edit_url, self.equipamento_payload())
        self.assertRedirects(denied, detail_url)

        self.client.force_login(self.owner)
        allowed = self.client.post(edit_url, self.equipamento_payload("CIN-101"))
        self.assertRedirects(allowed, detail_url)
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.identificador, "CIN-101")
        self.assertEqual(self.equipamento.atualizado_por, self.owner)

    def test_manager_edits_and_deletes_any_material(self):
        self.client.force_login(self.manager)
        edit_url = reverse("estoque:editar_equipamento", args=[self.equipamento.pk])
        response = self.client.post(edit_url, self.equipamento_payload("CIN-GER"))
        self.assertRedirects(
            response,
            reverse("estoque:detalhe_equipamento", args=[self.equipamento.pk]),
        )
        delete_url = reverse("estoque:excluir_equipamento", args=[self.equipamento.pk])
        self.assertRedirects(
            self.client.post(delete_url), reverse("estoque:listar_equipamentos")
        )
        self.assertFalse(Equipamento.objects.filter(pk=self.equipamento.pk).exists())

    def test_management_pages_render_without_template_errors(self):
        movimentacao = MovimentacaoMaterial.objects.create(
            equipamento=self.equipamento,
            nome="Pessoa de teste",
            matricula="MAT-RENDER",
            quantidade=1,
            criado_por=self.manager,
            atualizado_por=self.manager,
        )
        self.client.force_login(self.manager)

        urls = (
            reverse("estoque:cadastrar_movimentacao"),
            reverse("estoque:editar_movimentacao", args=[movimentacao.pk]),
            reverse("estoque:excluir_equipamento", args=[self.equipamento.pk]),
            reverse("estoque:listar_movimentacoes"),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_cannot_reduce_stock_below_open_loans(self):
        MovimentacaoMaterial.objects.create(
            equipamento=self.equipamento,
            nome="Pessoa de teste",
            matricula="MAT-REDUZIR",
            quantidade=2,
            criado_por=self.manager,
            atualizado_por=self.manager,
        )
        self.client.force_login(self.manager)
        payload = self.equipamento_payload()
        payload["quantidade"] = 1

        response = self.client.post(
            reverse("estoque:editar_equipamento", args=[self.equipamento.pk]),
            payload,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Existem 2 unidade(s) emprestada(s)")
        self.equipamento.refresh_from_db()
        self.assertEqual(self.equipamento.quantidade, 2)

    def test_filters_equipment_list_by_tonnage_capacity(self):
        Equipamento.objects.create(
            equipamento="MANILHA",
            identificador="MAN-015",
            caracteristica="Aço galvanizado",
            capacidade_toneladas="15.00",
            tipo_equipamento="MANUAL",
            quantidade=1,
            localizacao="ARMAZEM",
            criado_por=self.owner,
        )
        Equipamento.objects.create(
            equipamento="GANCHO",
            identificador="GAN-025",
            caracteristica="Gancho de alta resistência",
            capacidade_toneladas="25.00",
            tipo_equipamento="MANUAL",
            quantidade=1,
            localizacao="ARMAZEM",
            criado_por=self.owner,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("estoque:listar_equipamentos"),
            {"capacidade_min": "10,5", "capacidade_max": "20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MAN-015")
        self.assertNotContains(response, "CIN-100")
        self.assertNotContains(response, "GAN-025")
        self.assertContains(response, "15,00 t")

    def test_rejects_invalid_capacity_filter_without_server_error(self):
        self.client.force_login(self.owner)

        for invalid_value in ("vinte", "NaN", "Infinity", "-1", "100000000"):
            with self.subTest(invalid_value=invalid_value):
                response = self.client.get(
                    reverse("estoque:listar_equipamentos"),
                    {"capacidade_min": invalid_value, "capacidade_max": "10"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Informe uma capacidade mínima válida")

    def test_employee_can_create_and_management_can_return_loans(self):
        create_url = reverse("estoque:cadastrar_movimentacao")
        retirada = timezone.localtime().replace(second=0, microsecond=0)
        previsao = retirada + timedelta(days=7)
        payload = self.lote_payload(
            [(self.equipamento, 1)],
            data_retirada=retirada.strftime("%Y-%m-%dT%H:%M"),
            data_prevista_devolucao=previsao.strftime("%Y-%m-%dT%H:%M"),
        )

        self.client.force_login(self.owner)
        self.assertRedirects(
            self.client.post(create_url, payload), reverse("estoque:listar_movimentacoes")
        )
        movimentacao = MovimentacaoMaterial.objects.get()
        self.assertEqual(movimentacao.criado_por, self.owner)
        self.assertEqual(movimentacao.atualizado_por, self.owner)
        self.assertEqual(movimentacao.empresa_destino, "Empresa Parceira")
        self.assertEqual(
            timezone.localtime(movimentacao.data_prevista_devolucao), previsao
        )
        list_response = self.client.get(reverse("estoque:listar_movimentacoes"))
        self.assertContains(list_response, "Empresa Parceira")
        self.assertContains(list_response, previsao.strftime("%d/%m/%Y %H:%M"))

        self.client.force_login(self.manager)
        return_url = reverse("estoque:devolver_movimentacao", args=[movimentacao.pk])
        self.client.post(return_url)
        movimentacao.refresh_from_db()
        self.assertIsNotNone(movimentacao.data_devolucao)
        self.assertEqual(movimentacao.atualizado_por, self.manager)

    def test_rejects_expected_return_before_withdrawal(self):
        self.client.force_login(self.manager)
        retirada = timezone.localtime().replace(second=0, microsecond=0)
        response = self.client.post(
            reverse("estoque:cadastrar_movimentacao"),
            self.lote_payload(
                [(self.equipamento, 1)],
                nome="Pessoa de teste",
                matricula="MAT-ANTECIPADA",
                data_retirada=retirada.strftime("%Y-%m-%dT%H:%M"),
                data_prevista_devolucao=(retirada - timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "A previsão de devolução não pode ser anterior à retirada.",
        )
        self.assertFalse(MovimentacaoMaterial.objects.exists())

    def test_cannot_loan_more_than_available_stock(self):
        MovimentacaoMaterial.objects.create(
            equipamento=self.equipamento,
            nome="Primeiro colaborador",
            matricula="MAT-001",
            quantidade=2,
            criado_por=self.manager,
            atualizado_por=self.manager,
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("estoque:cadastrar_movimentacao"),
            self.lote_payload(
                [(self.equipamento, 1)],
                nome="Segundo colaborador",
                matricula="MAT-002",
                data_retirada=timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                data_prevista_devolucao="",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Há somente 0 unidade(s) disponível(is)")
        self.assertEqual(MovimentacaoMaterial.objects.count(), 1)

    def test_employee_creates_batch_with_different_quantities_and_audit(self):
        segundo = self.criar_equipamento("MAN-200", quantidade=5)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("estoque:cadastrar_movimentacao"),
            self.lote_payload([(self.equipamento, 1), (segundo, 3)]),
        )

        self.assertRedirects(response, reverse("estoque:listar_movimentacoes"))
        movimentacoes = list(
            MovimentacaoMaterial.objects.order_by("equipamento_id")
        )
        self.assertEqual(len(movimentacoes), 2)
        self.assertEqual(
            {(item.equipamento_id, item.quantidade) for item in movimentacoes},
            {(self.equipamento.pk, 1), (segundo.pk, 3)},
        )
        for movimentacao in movimentacoes:
            with self.subTest(movimentacao=movimentacao.pk):
                self.assertEqual(movimentacao.nome, "Maria Operadora")
                self.assertEqual(movimentacao.matricula, "MAT-100")
                self.assertEqual(movimentacao.empresa_destino, "Empresa Parceira")
                self.assertEqual(movimentacao.criado_por, self.owner)
                self.assertEqual(movimentacao.atualizado_por, self.owner)

        auditorias = AuditLog.objects.filter(
            user=self.owner,
            action="create",
            app_label="estoque",
            model_name="movimentacaomaterial",
        )
        self.assertEqual(auditorias.count(), 2)
        self.assertSetEqual(
            set(auditorias.values_list("object_pk", flat=True)),
            {str(item.pk) for item in movimentacoes},
        )

    def test_batch_rolls_back_every_item_when_one_has_insufficient_stock(self):
        sem_estoque = self.criar_equipamento("GAN-SEM", quantidade=1)
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("estoque:cadastrar_movimentacao"),
            self.lote_payload([(self.equipamento, 1), (sem_estoque, 2)]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Há somente 1 unidade(s) disponível(is)")
        self.assertFalse(MovimentacaoMaterial.objects.exists())
        self.assertFalse(
            AuditLog.objects.filter(
                action="create",
                app_label="estoque",
                model_name="movimentacaomaterial",
            ).exists()
        )

    def test_batch_rejects_repeated_equipment(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("estoque:cadastrar_movimentacao"),
            self.lote_payload([(self.equipamento, 1), (self.equipamento, 1)]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este material já foi adicionado à retirada.")
        self.assertFalse(MovimentacaoMaterial.objects.exists())

    def test_creator_get_only_confirms_and_post_deletes_loan(self):
        movimentacao = MovimentacaoMaterial.objects.create(
            equipamento=self.equipamento,
            nome="Empréstimo encerrado",
            matricula="MAT-EXCLUIR",
            quantidade=1,
            data_devolucao=timezone.now(),
            criado_por=self.owner,
            atualizado_por=self.manager,
        )
        delete_url = reverse("estoque:excluir_movimentacao", args=[movimentacao.pk])
        self.client.force_login(self.owner)

        get_response = self.client.get(delete_url)

        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Tem certeza")
        self.assertTrue(MovimentacaoMaterial.objects.filter(pk=movimentacao.pk).exists())

        post_response = self.client.post(delete_url)

        self.assertRedirects(post_response, reverse("estoque:listar_movimentacoes"))
        self.assertFalse(MovimentacaoMaterial.objects.filter(pk=movimentacao.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                user=self.owner,
                action="delete",
                app_label="estoque",
                model_name="movimentacaomaterial",
                object_pk=str(movimentacao.pk),
            ).exists()
        )

    def test_other_employee_cannot_delete_loan(self):
        movimentacao = MovimentacaoMaterial.objects.create(
            equipamento=self.equipamento,
            nome="Empréstimo de outro autor",
            matricula="MAT-OUTRO",
            quantidade=1,
            data_devolucao=timezone.now(),
            criado_por=self.owner,
            atualizado_por=self.owner,
        )
        delete_url = reverse("estoque:excluir_movimentacao", args=[movimentacao.pk])
        self.client.force_login(self.other)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(delete_url)
                self.assertRedirects(response, reverse("estoque:listar_movimentacoes"))
                self.assertTrue(
                    MovimentacaoMaterial.objects.filter(pk=movimentacao.pk).exists()
                )

    def test_manager_and_admin_can_delete_any_loan(self):
        for usuario in (self.manager, self.admin):
            movimentacao = MovimentacaoMaterial.objects.create(
                equipamento=self.equipamento,
                nome="Empréstimo gerenciado",
                matricula=f"MAT-{usuario.username}",
                quantidade=1,
                data_devolucao=timezone.now(),
                criado_por=self.owner,
                atualizado_por=self.owner,
            )
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.post(
                    reverse("estoque:excluir_movimentacao", args=[movimentacao.pk])
                )
                self.assertRedirects(
                    response, reverse("estoque:listar_movimentacoes")
                )
                self.assertFalse(
                    MovimentacaoMaterial.objects.filter(pk=movimentacao.pk).exists()
                )

    def test_qr_destination_redirects_to_latest_active_pdf(self):
        Certificacao.objects.create(
            equipamento=self.equipamento,
            nome_certificado="Manual",
            data_certificacao=timezone.localdate(),
            empresa_certificadora="Empresa",
            codigo_certificado="PDF-1",
            anexo="equipamentos/1/certificacoes/manual.pdf",
            criado_por=self.owner,
        )
        self.client.force_login(self.other)

        response = self.client.get(
            reverse("estoque:destino_qrcode", args=[self.equipamento.pk])
        )

        self.assertRedirects(
            response,
            "/media/equipamentos/1/certificacoes/manual.pdf",
            fetch_redirect_response=False,
        )


class UserAccessFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin_qa", password="AdminQA!2026"
        )
        self.employee = User.objects.create_user(
            "comum_qa", password="ComumQA!2026"
        )
        self.manager = User.objects.create_user(
            "gestor_qa", password="GestorQA!2026"
        )
        UserAccess.objects.create(user=self.admin)
        UserAccess.objects.create(user=self.employee)
        UserAccess.objects.create(user=self.manager)
        Colaborador.objects.create(
            user=self.employee,
            matricula="comum_qa",
            nome="Usuario Comum QA",
            area="OP",
            cargo="AUX",
        )
        Colaborador.objects.create(
            user=self.manager,
            matricula="gestor_qa",
            nome="Gestor QA",
            area="OP",
            cargo="SUP",
        )

    def test_admin_and_employee_can_log_in(self):
        admin_response = self.client.post(
            reverse("login"),
            {
                "matricula": "admin_qa",
                "senha": "AdminQA!2026",
            },
        )
        self.assertRedirects(admin_response, reverse("dashboard"))

        self.client.logout()
        employee_response = self.client.post(
            reverse("login"),
            {
                "matricula": "comum_qa",
                "senha": "ComumQA!2026",
            },
        )
        self.assertRedirects(employee_response, reverse("dashboard"))

    def test_anonymous_employee_and_manager_cannot_create_accounts(self):
        registration_url = reverse("estoque:cadastrar_colaborador")
        anonymous_response = self.client.get(registration_url)
        self.assertRedirects(
            anonymous_response,
            f"{reverse('login')}?next={registration_url}",
        )

        for user in (self.employee, self.manager):
            client = Client()
            client.force_login(user)
            response = client.get(registration_url)
            self.assertRedirects(response, reverse("estoque:dashboard"))

    @patch(
        "historico.security.generate_temporary_password",
        return_value="TemporariaQA!2026",
    )
    def test_admin_creates_account_and_new_user_changes_temporary_password(
        self, _password
    ):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("estoque:cadastrar_colaborador"),
            {
                "matricula": "novo_qa",
                "nome": "Novo Usuario QA",
                "area": "MAT",
                "cargo": "OPR1",
            },
        )

        self.assertRedirects(response, reverse("estoque:cadastrar_colaborador"))
        new_user = User.objects.get(username="novo_qa")
        self.assertTrue(new_user.check_password("TemporariaQA!2026"))
        self.assertTrue(new_user.access_control.must_change_password)

        self.client.logout()
        login_response = self.client.post(
            reverse("login"),
            {
                "matricula": "novo_qa",
                "senha": "TemporariaQA!2026",
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, reverse("dashboard"))
        self.assertRedirects(
            self.client.get(reverse("dashboard")), reverse("alterar_senha")
        )

        change_response = self.client.post(
            reverse("alterar_senha"),
            {
                "old_password": "TemporariaQA!2026",
                "new_password1": "NovaSenhaQA!2026Segura",
                "new_password2": "NovaSenhaQA!2026Segura",
            },
        )
        self.assertRedirects(change_response, reverse("dashboard"))
        new_user.refresh_from_db()
        access = UserAccess.objects.get(user=new_user)
        self.assertTrue(new_user.check_password("NovaSenhaQA!2026Segura"))
        self.assertFalse(access.must_change_password)

    def test_registration_form_does_not_collect_sensitive_data(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("estoque:cadastrar_colaborador"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="cpf"')
        self.assertNotContains(response, 'name="email"')

    @override_settings(AD_AUTH_ENABLED=True)
    def test_admin_pre_authorizes_ad_user_without_local_credentials(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estoque:cadastrar_colaborador"),
            {
                "matricula": "ad_qa",
                "nome": "Usuario AD QA",
                "area": "OP",
                "cargo": "AUX",
            },
        )

        self.assertRedirects(response, reverse("estoque:cadastrar_colaborador"))
        user = User.objects.get(username="ad_qa")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.email, "")
        self.assertTrue(UserAccess.objects.filter(user=user).exists())

    def test_registered_users_list_includes_admin_and_employee(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("estoque:listar_colaboradores"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin_qa")
        self.assertContains(response, "comum_qa")

    def test_registered_users_list_requires_authentication(self):
        list_url = reverse("estoque:listar_colaboradores")

        response = self.client.get(list_url)

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={list_url}",
        )

    def test_employee_and_manager_cannot_view_registered_users(self):
        list_url = reverse("estoque:listar_colaboradores")
        for user in (self.employee, self.manager):
            client = Client()
            client.force_login(user)

            response = client.get(list_url)

            self.assertRedirects(response, reverse("estoque:dashboard"))
            self.assertNotContains(response, "admin_qa", status_code=302)
            self.assertNotContains(response, "comum_qa", status_code=302)

    def test_user_management_menu_is_hidden_from_employee_and_manager(self):
        for user in (self.employee, self.manager):
            client = Client()
            client.force_login(user)

            response = client.get(reverse("dashboard"))

            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Usuários cadastrados")
            self.assertNotContains(response, "Autorizar usuário")

    def test_staff_admin_can_view_only_locally_authorized_accounts(self):
        staff_admin = User.objects.create_user(
            "staff_qa",
            password="StaffQA!2026",
            is_staff=True,
        )
        UserAccess.objects.create(user=staff_admin)
        User.objects.create_user("fora_useraccess", password="ForaQA!2026")
        client = Client()
        client.force_login(staff_admin)

        response = client.get(reverse("estoque:listar_colaboradores"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin_qa")
        self.assertContains(response, "comum_qa")
        self.assertContains(response, "gestor_qa")
        self.assertContains(response, "staff_qa")
        self.assertNotContains(response, "fora_useraccess")

    def test_registered_users_page_does_not_expose_sensitive_fields(self):
        self.admin.email = "admin.sensivel@empresa.com"
        self.admin.save(update_fields=["email"])
        self.client.force_login(self.admin)

        response = self.client.get(reverse("estoque:listar_colaboradores"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "admin.sensivel@empresa.com")
        self.assertNotContains(response, "CPF")
        self.assertNotContains(response, "<th>Senha</th>", html=True)
        self.assertNotContains(response, self.admin.password)

    def test_admin_revocation_removes_user_and_access_record(self):
        employee_id = self.employee.pk
        collaborator_id = self.employee.estoque_colaborador.pk
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("estoque:excluir_colaborador", args=[collaborator_id])
        )

        self.assertRedirects(response, reverse("estoque:listar_colaboradores"))
        self.assertFalse(User.objects.filter(pk=employee_id).exists())
        self.assertFalse(UserAccess.objects.filter(user_id=employee_id).exists())

    def test_employee_and_manager_cannot_edit_or_revoke_users(self):
        collaborator_id = self.employee.estoque_colaborador.pk
        edit_url = reverse("estoque:editar_colaborador", args=[collaborator_id])
        revoke_url = reverse("estoque:excluir_colaborador", args=[collaborator_id])

        for user in (self.employee, self.manager):
            client = Client()
            client.force_login(user)

            self.assertRedirects(client.get(edit_url), reverse("estoque:dashboard"))
            self.assertRedirects(
                client.post(revoke_url),
                reverse("estoque:dashboard"),
            )
            self.assertTrue(User.objects.filter(pk=self.employee.pk).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CertificacaoNotificationTests(TestCase):
    def setUp(self):
        self.qr_patcher = patch("estoque.models.qrcode.make", return_value=FakeQrCode())
        self.qr_patcher.start()
        self.user = User.objects.create_user(
            "gestor", email="gestor@empresa.com", password="senha"
        )
        self.equipamento = Equipamento.objects.create(
            equipamento="Cinta de elevação",
            identificador="CIN-001",
            tipo_equipamento="MANUAL",
            quantidade=1,
            localizacao="Armazém",
            criado_por=self.user,
        )

    def tearDown(self):
        self.qr_patcher.stop()

    def criar_certificado(self, **kwargs):
        dados = {
            "equipamento": self.equipamento,
            "nome_certificado": "Inspeção anual",
            "data_certificacao": date(2026, 1, 10),
            "data_vencimento": date(2026, 10, 22),
            "empresa_certificadora": "Certifica Brasil",
            "codigo_certificado": "CERT-001",
            "notificar_por_email": True,
            "email_notificacao": "seguranca@empresa.com",
            "criado_por": self.user,
        }
        dados.update(kwargs)
        return Certificacao.objects.create(**dados)

    def test_form_normalizes_multiple_notification_emails(self):
        form = CertificacaoForm(
            data={
                "nome_certificado": "Inspeção anual",
                "data_certificacao": "2026-01-10",
                "data_vencimento": "2026-10-22",
                "empresa_certificadora": "Certifica Brasil",
                "codigo_certificado": "CERT-FORM",
                "detalhes": "",
                "notificar_por_email": "on",
                "email_notificacao": (
                    "um@empresa.com, dois@empresa.com; UM@empresa.com"
                ),
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["email_notificacao"],
            "um@empresa.com; dois@empresa.com",
        )

    def test_status_usa_tres_meses_de_calendario(self):
        certificado = self.criar_certificado(data_vencimento=date(2026, 4, 30))

        self.assertEqual(
            Certificacao.adicionar_meses(date(2026, 1, 31), 3), date(2026, 4, 30)
        )
        self.assertEqual(
            certificado.status_vencimento_em(date(2026, 1, 31)), "vence_em_3_meses"
        )
        certificado.data_vencimento = date(2026, 5, 1)
        self.assertEqual(certificado.status_vencimento_em(date(2026, 1, 31)), "valido")

    def test_envia_uma_vez_e_reenvia_se_vencimento_mudar(self):
        certificado = self.criar_certificado()
        referencia = date(2026, 7, 22)

        primeiro = enviar_avisos_certificados(referencia=referencia)
        segundo = enviar_avisos_certificados(referencia=referencia)

        self.assertEqual(primeiro["enviados"], 1)
        self.assertEqual(segundo["enviados"], 0)
        self.assertEqual(len(mail.outbox), 1)
        certificado.refresh_from_db()
        self.assertEqual(certificado.vencimento_notificado, certificado.data_vencimento)

        certificado.data_vencimento = date(2026, 10, 21)
        certificado.save(update_fields=["data_vencimento"])
        terceiro = enviar_avisos_certificados(referencia=referencia)

        self.assertEqual(terceiro["enviados"], 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_nao_envia_sem_ativacao_ou_email(self):
        self.criar_certificado(notificar_por_email=False)
        self.criar_certificado(codigo_certificado="CERT-002", email_notificacao="")

        resultado = enviar_avisos_certificados(referencia=date(2026, 7, 22))

        self.assertEqual(resultado["enviados"], 0)
        self.assertEqual(mail.outbox, [])

    def test_envia_um_unico_aviso_para_varios_destinatarios(self):
        self.criar_certificado(
            email_notificacao=(
                "seguranca@empresa.com; manutencao@empresa.com, "
                "seguranca@empresa.com"
            )
        )

        resultado = enviar_avisos_certificados(referencia=date(2026, 7, 22))

        self.assertEqual(resultado, {"enviados": 1, "erros": []})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["seguranca@empresa.com", "manutencao@empresa.com"],
        )

    def test_comando_de_notificacao(self):
        hoje = timezone.localdate()
        self.criar_certificado(data_vencimento=Certificacao.adicionar_meses(hoje, 1))
        saida = StringIO()

        call_command("notificar_certificados", stdout=saida)

        self.assertIn("1 aviso(s) enviado(s).", saida.getvalue())


class CertificacaoViewTests(TestCase):
    def setUp(self):
        self.qr_patcher = patch("estoque.models.qrcode.make", return_value=FakeQrCode())
        self.qr_patcher.start()
        self.user = User.objects.create_user(
            "colaborador", email="colaborador@empresa.com", password="senha"
        )
        self.other_user = User.objects.create_user("outro", password="senha")
        UserAccess.objects.create(user=self.user)
        UserAccess.objects.create(user=self.other_user)
        self.equipamento = Equipamento.objects.create(
            equipamento="Manilha",
            identificador="MAN-001",
            tipo_equipamento="MANUAL",
            quantidade=2,
            localizacao="Galpão A",
            criado_por=self.user,
        )
        self.certificado = Certificacao.objects.create(
            equipamento=self.equipamento,
            nome_certificado="Ensaio de carga",
            data_certificacao=date(2026, 5, 1),
            data_vencimento=Certificacao.adicionar_meses(timezone.localdate(), 2),
            empresa_certificadora="Laboratório Portuário",
            codigo_certificado="EC-100",
            criado_por=self.user,
        )
        outro_equipamento = Equipamento.objects.create(
            equipamento="Gancho",
            identificador="GAN-009",
            tipo_equipamento="MANUAL",
            quantidade=1,
            localizacao="Galpão B",
            criado_por=self.other_user,
        )
        Certificacao.objects.create(
            equipamento=outro_equipamento,
            nome_certificado="Certificado oculto",
            data_certificacao=date(2026, 1, 1),
            empresa_certificadora="Outra empresa",
            codigo_certificado="OUT-1",
            criado_por=self.other_user,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.qr_patcher.stop()

    def test_lista_apenas_certificados_dos_materiais_visiveis(self):
        response = self.client.get(reverse("estoque:listar_certificados"))

        self.assertContains(response, "Ensaio de carga")
        self.assertNotContains(response, "Certificado oculto")
        self.assertContains(response, "Vence em até 3 meses")

    def test_salva_preferencia_de_notificacao(self):
        response = self.client.post(
            reverse("estoque:listar_certificados"),
            {
                "acao": "salvar_notificacao",
                "certificado_id": self.certificado.pk,
                "notificar_por_email": "on",
                "email_notificacao": "avisos@empresa.com",
            },
        )

        self.assertRedirects(response, reverse("estoque:listar_certificados"))
        self.certificado.refresh_from_db()
        self.assertTrue(self.certificado.notificar_por_email)
        self.assertEqual(self.certificado.email_notificacao, "avisos@empresa.com")

    def test_salva_varios_destinatarios_normalizados(self):
        response = self.client.post(
            reverse("estoque:listar_certificados"),
            {
                "acao": "salvar_notificacao",
                "certificado_id": self.certificado.pk,
                "notificar_por_email": "on",
                "email_notificacao": (
                    "avisos@empresa.com, manutencao@empresa.com\n"
                    "AVISOS@empresa.com"
                ),
            },
        )

        self.assertRedirects(response, reverse("estoque:listar_certificados"))
        self.certificado.refresh_from_db()
        self.assertEqual(
            self.certificado.email_notificacao,
            "avisos@empresa.com; manutencao@empresa.com",
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    )
    def test_exibe_diagnostico_quando_smtp_nao_esta_configurado(self):
        response = self.client.get(reverse("estoque:listar_certificados"))

        self.assertContains(response, "Envio de e-mail indisponível")
        self.assertContains(response, "SMTP não está configurado")

    def test_rejeita_email_invalido(self):
        self.client.post(
            reverse("estoque:listar_certificados"),
            {
                "acao": "salvar_notificacao",
                "certificado_id": self.certificado.pk,
                "notificar_por_email": "on",
                "email_notificacao": "email-invalido",
            },
        )

        self.certificado.refresh_from_db()
        self.assertFalse(self.certificado.notificar_por_email)

    def test_filtro_por_status(self):
        response = self.client.get(
            reverse("estoque:listar_certificados"),
            {
                "status": "vence_em_3_meses",
            },
        )

        self.assertContains(response, "Ensaio de carga")

    def test_edita_certificado_e_reabre_notificacao(self):
        self.certificado.vencimento_notificado = self.certificado.data_vencimento
        self.certificado.save(update_fields=["vencimento_notificado"])
        nova_validade = Certificacao.adicionar_meses(timezone.localdate(), 5)

        response = self.client.post(
            reverse("estoque:editar_certificacao", args=[self.certificado.pk]),
            {
                "nome_certificado": self.certificado.nome_certificado,
                "data_certificacao": self.certificado.data_certificacao,
                "data_vencimento": nova_validade,
                "empresa_certificadora": self.certificado.empresa_certificadora,
                "codigo_certificado": "EC-101",
                "detalhes": "Atualizado",
                "email_notificacao": "",
            },
        )

        self.assertRedirects(response, reverse("estoque:listar_certificados"))
        self.certificado.refresh_from_db()
        self.assertEqual(self.certificado.codigo_certificado, "EC-101")
        self.assertEqual(self.certificado.data_vencimento, nova_validade)
        self.assertIsNone(self.certificado.vencimento_notificado)

    def test_renovacao_preserva_certificado_anterior(self):
        response = self.client.post(
            reverse("estoque:renovar_certificacao", args=[self.certificado.pk]),
            {
                "nome_certificado": self.certificado.nome_certificado,
                "data_certificacao": timezone.localdate(),
                "data_vencimento": Certificacao.adicionar_meses(
                    timezone.localdate(), 12
                ),
                "empresa_certificadora": self.certificado.empresa_certificadora,
                "codigo_certificado": "EC-RENOVADO",
                "detalhes": "Renovação anual",
                "notificar_por_email": "on",
                "email_notificacao": "avisos@empresa.com",
            },
        )

        self.assertRedirects(response, reverse("estoque:listar_certificados"))
        self.certificado.refresh_from_db()
        renovado = Certificacao.objects.get(codigo_certificado="EC-RENOVADO")
        self.assertFalse(self.certificado.ativa)
        self.assertFalse(self.certificado.notificar_por_email)
        self.assertEqual(renovado.certificacao_anterior, self.certificado)
        self.assertTrue(renovado.ativa)

        lista = self.client.get(reverse("estoque:listar_certificados"))
        historico = self.client.get(
            reverse("estoque:listar_certificados"), {"historico": "1"}
        )
        self.assertNotContains(lista, "EC-100")
        self.assertContains(historico, "EC-100")

    def test_rejeita_anexo_de_certificado_que_nao_seja_pdf(self):
        response = self.client.post(
            reverse("estoque:editar_certificacao", args=[self.certificado.pk]),
            {
                "nome_certificado": self.certificado.nome_certificado,
                "data_certificacao": self.certificado.data_certificacao,
                "data_vencimento": self.certificado.data_vencimento,
                "empresa_certificadora": self.certificado.empresa_certificadora,
                "codigo_certificado": self.certificado.codigo_certificado,
                "email_notificacao": "",
                "anexo": SimpleUploadedFile(
                    "certificado.txt", b"conteudo", content_type="text/plain"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "extensão de arquivo “txt” não é permitida")
