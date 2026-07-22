from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from historico.models import UserAccess

from .models import Certificacao, Colaborador, Equipamento
from .services.certificacoes import enviar_avisos_certificados


class FakeQrCode:
    def save(self, buffer, format):
        buffer.write(b"fake-png")


class EquipamentoQrCodeTests(TestCase):
    @override_settings(PUBLIC_BASE_URL="https://app.example.com")
    def test_qrcode_uses_public_base_url_when_configured(self):
        with patch("estoque.models.qrcode.make", return_value=FakeQrCode()) as make_qrcode:
            Equipamento.objects.create(
                equipamento="Cinta",
                identificador="C-001",
                tipo_equipamento="MANUAL",
                quantidade=1,
                localizacao="Armazem",
            )

        make_qrcode.assert_called_once_with("https://app.example.com/estoque/dashboard/equipamentos/detalhe_equipamento/1/")


class UserAccessFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            'admin_qa', email='admin.qa@empresa.com', password='AdminQA!2026'
        )
        self.employee = User.objects.create_user(
            'comum_qa', email='comum.qa@empresa.com', password='ComumQA!2026'
        )
        Colaborador.objects.create(
            user=self.employee,
            matricula='comum_qa',
            nome='Usuario Comum QA',
            email='comum.qa@empresa.com',
            cpf='111.222.333-44',
            area='OP',
            cargo='AUX',
        )

    def test_admin_and_employee_can_log_in(self):
        admin_response = self.client.post(reverse('login'), {
            'matricula': 'admin_qa',
            'senha': 'AdminQA!2026',
        })
        self.assertRedirects(admin_response, reverse('dashboard'))

        self.client.logout()
        employee_response = self.client.post(reverse('login'), {
            'matricula': 'comum_qa',
            'senha': 'ComumQA!2026',
        })
        self.assertRedirects(employee_response, reverse('dashboard'))

    def test_anonymous_and_employee_cannot_create_accounts(self):
        registration_url = reverse('estoque:cadastrar_colaborador')
        anonymous_response = self.client.get(registration_url)
        self.assertRedirects(
            anonymous_response,
            f"{reverse('login')}?next={registration_url}",
        )

        self.client.force_login(self.employee)
        employee_response = self.client.get(registration_url)
        self.assertRedirects(employee_response, reverse('estoque:dashboard'))

    @patch('historico.security.generate_temporary_password', return_value='TemporariaQA!2026')
    def test_admin_creates_account_and_new_user_changes_temporary_password(self, _password):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('estoque:cadastrar_colaborador'), {
            'matricula': 'novo_qa',
            'nome': 'Novo Usuario QA',
            'email': 'novo.qa@empresa.com',
            'cpf': '555.666.777-88',
            'area': 'MAT',
            'cargo': 'OPR1',
        })

        self.assertRedirects(response, reverse('estoque:cadastrar_colaborador'))
        new_user = User.objects.get(username='novo_qa')
        self.assertTrue(new_user.check_password('TemporariaQA!2026'))
        self.assertTrue(new_user.access_control.must_change_password)

        self.client.logout()
        login_response = self.client.post(reverse('login'), {
            'matricula': 'novo_qa',
            'senha': 'TemporariaQA!2026',
        })
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, reverse('dashboard'))
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('alterar_senha'))

        change_response = self.client.post(reverse('alterar_senha'), {
            'old_password': 'TemporariaQA!2026',
            'new_password1': 'NovaSenhaQA!2026Segura',
            'new_password2': 'NovaSenhaQA!2026Segura',
        })
        self.assertRedirects(change_response, reverse('dashboard'))
        new_user.refresh_from_db()
        access = UserAccess.objects.get(user=new_user)
        self.assertTrue(new_user.check_password('NovaSenhaQA!2026Segura'))
        self.assertFalse(access.must_change_password)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CertificacaoNotificationTests(TestCase):
    def setUp(self):
        self.qr_patcher = patch('estoque.models.qrcode.make', return_value=FakeQrCode())
        self.qr_patcher.start()
        self.user = User.objects.create_user('gestor', email='gestor@empresa.com', password='senha')
        self.equipamento = Equipamento.objects.create(
            equipamento='Cinta de elevação',
            identificador='CIN-001',
            tipo_equipamento='MANUAL',
            quantidade=1,
            localizacao='Armazém',
            criado_por=self.user,
        )

    def tearDown(self):
        self.qr_patcher.stop()

    def criar_certificado(self, **kwargs):
        dados = {
            'equipamento': self.equipamento,
            'nome_certificado': 'Inspeção anual',
            'data_certificacao': date(2026, 1, 10),
            'data_vencimento': date(2026, 10, 22),
            'empresa_certificadora': 'Certifica Brasil',
            'codigo_certificado': 'CERT-001',
            'notificar_por_email': True,
            'email_notificacao': 'seguranca@empresa.com',
            'criado_por': self.user,
        }
        dados.update(kwargs)
        return Certificacao.objects.create(**dados)

    def test_status_usa_tres_meses_de_calendario(self):
        certificado = self.criar_certificado(data_vencimento=date(2026, 4, 30))

        self.assertEqual(Certificacao.adicionar_meses(date(2026, 1, 31), 3), date(2026, 4, 30))
        self.assertEqual(certificado.status_vencimento_em(date(2026, 1, 31)), 'vence_em_3_meses')
        certificado.data_vencimento = date(2026, 5, 1)
        self.assertEqual(certificado.status_vencimento_em(date(2026, 1, 31)), 'valido')

    def test_envia_uma_vez_e_reenvia_se_vencimento_mudar(self):
        certificado = self.criar_certificado()
        referencia = date(2026, 7, 22)

        primeiro = enviar_avisos_certificados(referencia=referencia)
        segundo = enviar_avisos_certificados(referencia=referencia)

        self.assertEqual(primeiro['enviados'], 1)
        self.assertEqual(segundo['enviados'], 0)
        self.assertEqual(len(mail.outbox), 1)
        certificado.refresh_from_db()
        self.assertEqual(certificado.vencimento_notificado, certificado.data_vencimento)

        certificado.data_vencimento = date(2026, 10, 21)
        certificado.save(update_fields=['data_vencimento'])
        terceiro = enviar_avisos_certificados(referencia=referencia)

        self.assertEqual(terceiro['enviados'], 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_nao_envia_sem_ativacao_ou_email(self):
        self.criar_certificado(notificar_por_email=False)
        self.criar_certificado(codigo_certificado='CERT-002', email_notificacao='')

        resultado = enviar_avisos_certificados(referencia=date(2026, 7, 22))

        self.assertEqual(resultado['enviados'], 0)
        self.assertEqual(mail.outbox, [])

    def test_comando_de_notificacao(self):
        hoje = timezone.localdate()
        self.criar_certificado(data_vencimento=Certificacao.adicionar_meses(hoje, 1))
        saida = StringIO()

        call_command('notificar_certificados', stdout=saida)

        self.assertIn('1 aviso(s) enviado(s).', saida.getvalue())


class CertificacaoViewTests(TestCase):
    def setUp(self):
        self.qr_patcher = patch('estoque.models.qrcode.make', return_value=FakeQrCode())
        self.qr_patcher.start()
        self.user = User.objects.create_user(
            'colaborador', email='colaborador@empresa.com', password='senha'
        )
        self.other_user = User.objects.create_user('outro', password='senha')
        self.equipamento = Equipamento.objects.create(
            equipamento='Manilha',
            identificador='MAN-001',
            tipo_equipamento='MANUAL',
            quantidade=2,
            localizacao='Galpão A',
            criado_por=self.user,
        )
        self.certificado = Certificacao.objects.create(
            equipamento=self.equipamento,
            nome_certificado='Ensaio de carga',
            data_certificacao=date(2026, 5, 1),
            data_vencimento=Certificacao.adicionar_meses(timezone.localdate(), 2),
            empresa_certificadora='Laboratório Portuário',
            codigo_certificado='EC-100',
            criado_por=self.user,
        )
        outro_equipamento = Equipamento.objects.create(
            equipamento='Gancho',
            identificador='GAN-009',
            tipo_equipamento='MANUAL',
            quantidade=1,
            localizacao='Galpão B',
            criado_por=self.other_user,
        )
        Certificacao.objects.create(
            equipamento=outro_equipamento,
            nome_certificado='Certificado oculto',
            data_certificacao=date(2026, 1, 1),
            empresa_certificadora='Outra empresa',
            codigo_certificado='OUT-1',
            criado_por=self.other_user,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.qr_patcher.stop()

    def test_lista_apenas_certificados_dos_materiais_visiveis(self):
        response = self.client.get(reverse('estoque:listar_certificados'))

        self.assertContains(response, 'Ensaio de carga')
        self.assertNotContains(response, 'Certificado oculto')
        self.assertContains(response, 'Vence em até 3 meses')

    def test_salva_preferencia_de_notificacao(self):
        response = self.client.post(reverse('estoque:listar_certificados'), {
            'acao': 'salvar_notificacao',
            'certificado_id': self.certificado.pk,
            'notificar_por_email': 'on',
            'email_notificacao': 'avisos@empresa.com',
        })

        self.assertRedirects(response, reverse('estoque:listar_certificados'))
        self.certificado.refresh_from_db()
        self.assertTrue(self.certificado.notificar_por_email)
        self.assertEqual(self.certificado.email_notificacao, 'avisos@empresa.com')

    def test_rejeita_email_invalido(self):
        self.client.post(reverse('estoque:listar_certificados'), {
            'acao': 'salvar_notificacao',
            'certificado_id': self.certificado.pk,
            'notificar_por_email': 'on',
            'email_notificacao': 'email-invalido',
        })

        self.certificado.refresh_from_db()
        self.assertFalse(self.certificado.notificar_por_email)

    def test_filtro_por_status(self):
        response = self.client.get(reverse('estoque:listar_certificados'), {
            'status': 'vence_em_3_meses',
        })

        self.assertContains(response, 'Ensaio de carga')

    def test_edita_certificado_e_reabre_notificacao(self):
        self.certificado.vencimento_notificado = self.certificado.data_vencimento
        self.certificado.save(update_fields=['vencimento_notificado'])
        nova_validade = Certificacao.adicionar_meses(timezone.localdate(), 5)

        response = self.client.post(
            reverse('estoque:editar_certificacao', args=[self.certificado.pk]),
            {
                'nome_certificado': self.certificado.nome_certificado,
                'data_certificacao': self.certificado.data_certificacao,
                'data_vencimento': nova_validade,
                'empresa_certificadora': self.certificado.empresa_certificadora,
                'codigo_certificado': 'EC-101',
                'detalhes': 'Atualizado',
                'email_notificacao': '',
            },
        )

        self.assertRedirects(response, reverse('estoque:listar_certificados'))
        self.certificado.refresh_from_db()
        self.assertEqual(self.certificado.codigo_certificado, 'EC-101')
        self.assertEqual(self.certificado.data_vencimento, nova_validade)
        self.assertIsNone(self.certificado.vencimento_notificado)

    def test_renovacao_preserva_certificado_anterior(self):
        response = self.client.post(
            reverse('estoque:renovar_certificacao', args=[self.certificado.pk]),
            {
                'nome_certificado': self.certificado.nome_certificado,
                'data_certificacao': timezone.localdate(),
                'data_vencimento': Certificacao.adicionar_meses(timezone.localdate(), 12),
                'empresa_certificadora': self.certificado.empresa_certificadora,
                'codigo_certificado': 'EC-RENOVADO',
                'detalhes': 'Renovação anual',
                'notificar_por_email': 'on',
                'email_notificacao': 'avisos@empresa.com',
            },
        )

        self.assertRedirects(response, reverse('estoque:listar_certificados'))
        self.certificado.refresh_from_db()
        renovado = Certificacao.objects.get(codigo_certificado='EC-RENOVADO')
        self.assertFalse(self.certificado.ativa)
        self.assertFalse(self.certificado.notificar_por_email)
        self.assertEqual(renovado.certificacao_anterior, self.certificado)
        self.assertTrue(renovado.ativa)

        lista = self.client.get(reverse('estoque:listar_certificados'))
        historico = self.client.get(reverse('estoque:listar_certificados'), {'historico': '1'})
        self.assertNotContains(lista, 'EC-100')
        self.assertContains(historico, 'EC-100')

    def test_rejeita_anexo_de_certificado_que_nao_seja_pdf(self):
        response = self.client.post(
            reverse('estoque:editar_certificacao', args=[self.certificado.pk]),
            {
                'nome_certificado': self.certificado.nome_certificado,
                'data_certificacao': self.certificado.data_certificacao,
                'data_vencimento': self.certificado.data_vencimento,
                'empresa_certificadora': self.certificado.empresa_certificadora,
                'codigo_certificado': self.certificado.codigo_certificado,
                'email_notificacao': '',
                'anexo': SimpleUploadedFile('certificado.txt', b'conteudo', content_type='text/plain'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'extensão de arquivo “txt” não é permitida')
