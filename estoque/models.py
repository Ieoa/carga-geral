import calendar
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import qrcode
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now


class Colaborador(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="estoque_colaborador",
    )
    matricula = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    data_criacao = models.DateTimeField(default=timezone.now)

    AREA_CHOICES = [
        ("OP", "Operações"),
        ("ARM", "Armazém"),
        ("MAT", "Materiais"),
        ("MANU", "Manutenção"),
    ]

    CARGO_CHOICES = [
        ("GER", "Gerente"),
        ("CORD", "Coordenador"),
        ("SUP", "Supervisor"),
        ("OPR1", "Operador I"),
        ("OPR2", "Operador II"),
        ("AUX", "Auxiliar"),
    ]

    area = models.CharField(max_length=6, choices=AREA_CHOICES)
    cargo = models.CharField(max_length=6, choices=CARGO_CHOICES)

    def save(self, *args, **kwargs):
        self.nome = " ".join(word.capitalize() for word in self.nome.split())
        if not self.data_criacao:
            self.data_criacao = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.matricula})"


def caminho_foto(instance, filename):
    registro = instance.registro or "novo"
    return f"equipamentos/{registro}/fotos/{Path(filename).name}"


def caminho_qrcode(instance, filename):
    registro = instance.registro or "novo"
    return f"equipamentos/{registro}/qrcodes/{Path(filename).name}"


def caminho_anexo(instance, filename):
    """Mantido para compatibilidade com a migration histórica 0008."""
    registro = instance.registro or "novo"
    return f"equipamentos/{registro}/anexos/{Path(filename).name}"


def caminho_certificacao(instance, filename):
    equipamento_id = instance.equipamento_id or "sem_equipamento"
    return f"equipamentos/{equipamento_id}/certificacoes/{Path(filename).name}"


class Equipamento(models.Model):
    QR_CODE_VERSION = 2

    registro = models.AutoField(primary_key=True)  # número único automático
    equipamento = models.CharField(max_length=100)
    identificador = models.CharField(max_length=50)
    caracteristica = models.TextField(blank=True, null=True)
    descricao_uso = models.TextField(blank=True, null=True)

    TIPO_CHOICES = [
        ("ELETRICO", "Elétrico"),
        ("MANUAL", "Manual"),
        ("HIDRAULICO", "Hidráulico"),
        ("PNEUMATICO", "Pneumático"),
        ("OUTRO", "Outro"),
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
        return reverse("estoque:detalhe_equipamento", args=[str(self.pk)])

    def get_qr_url(self):
        return reverse("estoque:destino_qrcode", args=[str(self.pk)])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        expected_prefix = f"qrcode_v{self.QR_CODE_VERSION}_{self.registro}"
        current_name = Path(self.qrcode.name).name if self.qrcode else ""
        if current_name.startswith(expected_prefix):
            return

        self.gerar_qrcode(force=True, using=kwargs.get("using"))

    def gerar_qrcode(self, *, force=False, using=None):
        """Gera um QR que abre o PDF ativo mais recente deste material."""
        if self.qrcode and not force:
            return

        detail_path = self.get_qr_url()
        public_base_url = getattr(settings, "PUBLIC_BASE_URL", "")
        qr_data = (
            urljoin(f"{public_base_url.rstrip('/')}/", detail_path.lstrip("/"))
            if public_base_url
            else detail_path
        )
        qr = qrcode.make(qr_data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        file_name = f"qrcode_v{self.QR_CODE_VERSION}_{self.registro}.png"
        self.qrcode.save(file_name, File(buffer), save=False)

        super().save(update_fields=["qrcode"], using=using)


class Certificacao(models.Model):
    equipamento = models.ForeignKey(
        Equipamento, on_delete=models.CASCADE, related_name="certificacoes"
    )
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
        validators=[FileExtensionValidator(["pdf"])],
    )
    ativa = models.BooleanField(default=True)
    certificacao_anterior = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renovacoes",
    )
    notificar_por_email = models.BooleanField(default=False)
    email_notificacao = models.TextField(blank=True, default="")
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
        related_name="certificacoes_atualizadas",
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
            return "substituido"
        referencia = referencia or timezone.localdate()
        if not self.data_vencimento:
            return "sem_vencimento"
        if self.data_vencimento < referencia:
            return "vencido"
        if self.data_vencimento <= self.adicionar_meses(referencia, 3):
            return "vence_em_3_meses"
        return "valido"

    @property
    def status_vencimento(self):
        return self.status_vencimento_em()

    @property
    def rotulo_status_vencimento(self):
        return {
            "vencido": "Vencido",
            "vence_em_3_meses": "Vence em até 3 meses",
            "valido": "Válido",
            "sem_vencimento": "Sem vencimento",
            "substituido": "Substituído",
        }[self.status_vencimento]

    @property
    def classe_status_vencimento(self):
        return {
            "vencido": "danger",
            "vence_em_3_meses": "warning",
            "valido": "success",
            "sem_vencimento": "secondary",
            "substituido": "dark",
        }[self.status_vencimento]

    @property
    def dias_para_vencimento(self):
        if not self.data_vencimento:
            return None
        return (self.data_vencimento - timezone.localdate()).days


class MovimentacaoMaterial(models.Model):
    equipamento = models.ForeignKey(
        Equipamento,
        on_delete=models.PROTECT,
        related_name="movimentacoes",
    )
    nome = models.CharField("Nome", max_length=150)
    matricula = models.CharField("Matrícula", max_length=30)
    empresa_destino = models.CharField(
        "Empresa ou destino",
        max_length=150,
        blank=True,
    )
    quantidade = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    data_retirada = models.DateTimeField("Data e hora da retirada", default=now)
    data_prevista_devolucao = models.DateTimeField(
        "Previsão de devolução",
        null=True,
        blank=True,
    )
    data_devolucao = models.DateTimeField(
        "Data e hora da devolução",
        null=True,
        blank=True,
    )
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_material_criadas",
    )
    atualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_material_atualizadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_retirada", "-pk"]
        verbose_name = "empréstimo de material"
        verbose_name_plural = "empréstimos de materiais"

    def __str__(self):
        return f"{self.equipamento} cedido para {self.nome} ({self.matricula})"

    @property
    def devolvido(self):
        return self.data_devolucao is not None

    @property
    def atrasado(self):
        return bool(
            not self.data_devolucao
            and self.data_prevista_devolucao
            and self.data_prevista_devolucao < timezone.now()
        )
