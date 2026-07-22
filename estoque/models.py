from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator, RegexValidator
from django.utils import timezone
import qrcode
from io import BytesIO
from django.core.files import File
from django.conf import settings
from django.utils.timezone import now
from django.urls import reverse
from pathlib import Path
from urllib.parse import urljoin
import calendar

class Colaborador(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='estoque_colaborador',
    )
    matricula = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    cpf = models.CharField(
        max_length=14,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{3}\.\d{3}\.\d{3}-\d{2}$',
                message='CPF deve estar no formato: 000.000.000-00'
            )
        ]
    )
    data_criacao = models.DateTimeField(default=timezone.now)  # Correção aqui
    
    AREA_CHOICES = [
        ('OP', 'Operações'),
        ('ARM', 'Armazém'),
        ('MAT', 'Materiais'),
        ('MANU', 'Manutenção'),
    ]
    
    CARGO_CHOICES = [
        ('GER', 'Gerente'),
        ('CORD', 'Coordenador'),
        ('SUP', 'Supervisor'),
        ('OPR1', 'Operador I'),
        ('OPR2', 'Operador II'),
        ('AUX', 'Auxiliar'),
    ]
    
    area = models.CharField(max_length=6, choices=AREA_CHOICES)
    cargo = models.CharField(max_length=6, choices=CARGO_CHOICES)
    
    def save(self, *args, **kwargs):
        # Formata o nome com iniciais maiúsculas
        self.nome = ' '.join(word.capitalize() for word in self.nome.split())
        if not self.data_criacao:  # Se não tiver data de criação
            self.data_criacao = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nome} ({self.matricula})"
    
    


# Crienado modelo de registro de equipamentos junto com QR Code


def caminho_foto(instance, filename):
    registro = instance.registro or "novo"
    return f'equipamentos/{registro}/fotos/{Path(filename).name}'

def caminho_qrcode(instance, filename):
    registro = instance.registro or "novo"
    return f'equipamentos/{registro}/qrcodes/{Path(filename).name}'

def caminho_anexo(instance, filename):
    registro = instance.registro or "novo"
    return f'equipamentos/{registro}/anexos/{Path(filename).name}'


def caminho_certificacao(instance, filename):
    equipamento_id = instance.equipamento_id or "sem_equipamento"
    return f"equipamentos/{equipamento_id}/certificacoes/{Path(filename).name}"

class Equipamento(models.Model):
    registro = models.AutoField(primary_key=True)  # número único automático
    equipamento = models.CharField(max_length=100)
    identificador = models.CharField(max_length=50)
    caracteristica = models.TextField(blank=True, null=True)
    descricao_uso = models.TextField(blank=True, null=True)

    TIPO_CHOICES = [
        ('ELETRICO', 'Elétrico'),
        ('MANUAL', 'Manual'),
        ('HIDRAULICO', 'Hidráulico'),
        ('PNEUMATICO', 'Pneumático'),
        ('OUTRO', 'Outro'),
    ]
    tipo_equipamento = models.CharField(max_length=20, choices=TIPO_CHOICES)

    quantidade = models.PositiveIntegerField(default=1)
    localizacao = models.CharField(max_length=100)
    foto = models.ImageField(upload_to=caminho_foto, null=True, blank=True)
    qrcode = models.ImageField(upload_to=caminho_qrcode, blank=True)
    data_cadastro = models.DateTimeField(default=now)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipamentos_criados",
    )
    atualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipamentos_atualizados",
    )

    def __str__(self):
        return f"{self.equipamento} ({self.identificador})"

    def get_absolute_url(self):
        return reverse('estoque:detalhe_equipamento', args=[str(self.pk)])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        detail_path = self.get_absolute_url()
        public_base_url = getattr(settings, "PUBLIC_BASE_URL", "")
        qr_data = (
            urljoin(f"{public_base_url.rstrip('/')}/", detail_path.lstrip("/"))
            if public_base_url
            else detail_path
        )
        qr = qrcode.make(qr_data)
        buffer = BytesIO()
        qr.save(buffer, format='PNG')
        file_name = f'qrcode_{self.registro}.png'
        self.qrcode.save(file_name, File(buffer), save=False)

        super().save(update_fields=["qrcode"], using=kwargs.get("using"))

class Certificacao(models.Model):
    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name='certificacoes')
    nome_certificado = models.CharField(max_length=100)  # Ex: ISO 9001
    data_certificacao = models.DateField()
    data_vencimento = models.DateField(null=True, blank=True)
    empresa_certificadora = models.CharField(max_length=100)
    codigo_certificado = models.CharField(max_length=50)
    detalhes = models.TextField(blank=True, null=True)
    anexo = models.FileField(
        upload_to=caminho_certificacao,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['pdf'])],
    )
    ativa = models.BooleanField(default=True)
    certificacao_anterior = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renovacoes',
    )
    notificar_por_email = models.BooleanField(default=False)
    email_notificacao = models.EmailField(blank=True, default='')
    notificacao_enviada_em = models.DateTimeField(null=True, blank=True)
    vencimento_notificado = models.DateField(null=True, blank=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificacoes_criadas",
    )
    atualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificacoes_atualizadas',
    )

    def __str__(self):
        return f"{self.nome_certificado} - {self.equipamento}"

    @staticmethod
    def adicionar_meses(data, meses):
        mes = data.month - 1 + meses
        ano = data.year + mes // 12
        mes = mes % 12 + 1
        dia = min(data.day, calendar.monthrange(ano, mes)[1])
        return data.replace(year=ano, month=mes, day=dia)

    def status_vencimento_em(self, referencia=None):
        if not self.ativa:
            return 'substituido'
        referencia = referencia or timezone.localdate()
        if not self.data_vencimento:
            return 'sem_vencimento'
        if self.data_vencimento < referencia:
            return 'vencido'
        if self.data_vencimento <= self.adicionar_meses(referencia, 3):
            return 'vence_em_3_meses'
        return 'valido'

    @property
    def status_vencimento(self):
        return self.status_vencimento_em()

    @property
    def rotulo_status_vencimento(self):
        return {
            'vencido': 'Vencido',
            'vence_em_3_meses': 'Vence em até 3 meses',
            'valido': 'Válido',
            'sem_vencimento': 'Sem vencimento',
            'substituido': 'Substituído',
        }[self.status_vencimento]

    @property
    def classe_status_vencimento(self):
        return {
            'vencido': 'danger',
            'vence_em_3_meses': 'warning',
            'valido': 'success',
            'sem_vencimento': 'secondary',
            'substituido': 'dark',
        }[self.status_vencimento]

    @property
    def dias_para_vencimento(self):
        if not self.data_vencimento:
            return None
        return (self.data_vencimento - timezone.localdate()).days
    
    
  
