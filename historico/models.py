from pathlib import Path

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


def navio_media_path(instance, filename):
    navio_id = instance.navio_id or "sem_navio"
    return f"navios/{navio_id}/midias/{Path(filename).name}"


def navio_documento_path(instance, filename):
    navio_id = instance.navio_id or "sem_navio"
    return f"navios/{navio_id}/documentos/{Path(filename).name}"


class Colaborador(models.Model):
    CARGO_CHOICES = [
        ("GER", "Gerente"),
        ("CORD", "Coordenador"),
        ("SUP", "Supervisor"),
        ("AUX", "Auxiliar"),
    ]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="colaborador"
    )
    nome = models.CharField(max_length=50)
    sobrenome = models.CharField(max_length=50)
    matricula = models.CharField(max_length=20, unique=True)
    cargo = models.CharField(max_length=6, choices=CARGO_CHOICES)
    data_criacao = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nome} {self.sobrenome} ({self.matricula})"


# Sinal para atualizar o User quando o Colaborador for atualizado
@receiver(post_save, sender=Colaborador)
def update_user_for_colaborador(sender, instance, **kwargs):
    """
    Sinal para atualizar o User quando um Colaborador for atualizado
    """
    # Verificar se o User já existe (não é uma nova instância)
    if instance.user_id:
        instance.user.username = instance.matricula
        instance.user.first_name = instance.nome
        instance.user.last_name = instance.sobrenome
        instance.user.save(update_fields=["username", "first_name", "last_name"])


class UserAccess(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="access_control"
    )
    must_change_password = models.BooleanField(default=False)
    temporary_password_created_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Controle de acesso de {self.user.username}"


class Navio(models.Model):
    BORDO_CHOICES = [
        ("BB", "Bombordo"),
        ("BE", "Boreste"),
    ]

    navio = models.CharField(max_length=100, blank=True, null=True)
    boca = models.CharField(max_length=50, blank=True, null=True)
    loa = models.CharField(max_length=50, blank=True, null=True)
    armador = models.CharField(max_length=100, blank=True, null=True)
    agencia = models.CharField(max_length=100, blank=True, null=True)
    bordo = models.CharField(
        max_length=50, choices=BORDO_CHOICES, blank=True, null=True
    )
    eta = models.DateTimeField("ETA", blank=True, null=True)
    pob = models.DateTimeField("POB", blank=True, null=True)
    inicio_operacao = models.DateTimeField("Início Operação", blank=True, null=True)
    fim_operacao = models.DateTimeField("Termino Operação", blank=True, null=True)

    ternos = models.IntegerField(blank=True, null=True)
    tempo_operacao = models.DurationField("Tempo de Operação", null=True, blank=True)
    volume_descarga = models.CharField(max_length=100, blank=True, null=True)
    peso_descarga = models.CharField(max_length=100, blank=True, null=True)
    volume_embarque = models.CharField(max_length=100, blank=True, null=True)
    peso_embarque = models.CharField(max_length=100, blank=True, null=True)

    criado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="navios",
    )
    atualizado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="navios_atualizados",
    )

    def __str__(self):
        return f"{self.armador or '---'} - {self.navio or '---'}"


class FotoVideoNavio(models.Model):
    navio = models.ForeignKey(Navio, on_delete=models.CASCADE, related_name="midias")
    arquivo = models.FileField(upload_to=navio_media_path)
    observacao = models.TextField(blank=True, null=True)
    tipo_peca = models.CharField(max_length=50, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias_navio",
    )

    def is_image(self):
        return self.arquivo.name.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))

    def is_video(self):
        return self.arquivo.name.lower().endswith((".mp4", ".avi", ".mov"))


class DocumentoNavio(models.Model):
    navio = models.ForeignKey(
        Navio, on_delete=models.CASCADE, related_name="documentos"
    )
    arquivo = models.FileField(upload_to=navio_documento_path)
    criado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_navio",
    )


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "Criação"),
        ("update", "Alteração"),
        ("delete", "Exclusão"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    actor_role = models.CharField(max_length=30, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    app_label = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80)
    object_pk = models.CharField(max_length=80)
    object_repr = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.object_repr}"
