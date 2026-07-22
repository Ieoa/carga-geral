from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Certificacao, Equipamento
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
