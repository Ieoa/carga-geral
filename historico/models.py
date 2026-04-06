
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class Colaborador(models.Model):
    
    CARGO_CHOICES = [
        ('GER', 'Gerente'),
        ('CORD', 'Coordenador'),
        ('SUP', 'Supervisor'),        
        ('AUX', 'Auxiliar'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="colaborador")    
    nome = models.CharField(max_length=50)
    sobrenome = models.CharField(max_length=50)
    matricula = models.CharField(max_length=20, unique=True)    
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
    
    email = models.EmailField(unique=True)
    cargo = models.CharField(max_length=6, choices=CARGO_CHOICES)
    data_criacao = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.nome} {self.sobrenome} ({self.matricula})"

    def save(self, *args, **kwargs):
        # Se for um novo Colaborador (não existe no banco)
        if not self.pk:
            # Limpa o CPF (remove pontos e traço)
            cpf_limpo = ''.join(filter(str.isdigit, self.cpf))
            senha = cpf_limpo[:6]  # Primeiros 6 dígitos

            # Cria o User associado
            user = User.objects.create_user(
                username=self.matricula,
                email=self.email,
                password=senha,
                first_name=self.nome,
                last_name=self.sobrenome
            )
            self.user = user  # Associa o User ao Colaborador

        # Chama o método save original para salvar o Colaborador
        super().save(*args, **kwargs)

# Sinal para atualizar o User quando o Colaborador for atualizado
@receiver(post_save, sender=Colaborador)
def update_user_for_colaborador(sender, instance, **kwargs):
    """
    Sinal para atualizar o User quando um Colaborador for atualizado
    """
    # Verificar se o User já existe (não é uma nova instância)
    if instance.user_id:
        instance.user.username = instance.matricula
        instance.user.email = instance.email
        instance.user.first_name = instance.nome
        instance.user.last_name = instance.sobrenome
        instance.user.save()
        
        
        
class Navio(models.Model):
    
    BORDO_CHOICES = [
        ('BB', 'Bombordo'),
        ('BE', 'Boreste'),
    ]
    
    navio = models.CharField(max_length=100, blank=True, null=True)
    boca = models.CharField(max_length=50, blank=True, null=True)
    loa = models.CharField(max_length=50, blank=True, null=True)
    armador = models.CharField(max_length=100, blank=True, null=True)
    agencia = models.CharField(max_length=100, blank=True, null=True)
    bordo = models.CharField(max_length=50, choices=BORDO_CHOICES, blank=True, null=True)
    eta = models.DateTimeField("ETA", blank=True, null=True)
    pob = models.DateTimeField("POB", blank=True, null=True)    
    inicio_operacao = models.DateTimeField("Início Operação", blank=True, null=True)
    fim_operacao = models.DateTimeField("Termino Operação", blank=True, null=True)

    # Ternos pode ficar opcional também
    ternos = models.IntegerField(blank=True, null=True)

    # Em horas → pode usar CharField se não precisar calcular
    tempo_operacao = models.DurationField("Tempo de Operação", null=True, blank=True)

    # Texto para permitir valores variados
    volume_descarga = models.CharField(blank=True, null=True)
    peso_descarga = models.CharField(blank=True, null=True)
    volume_embarque = models.CharField(blank=True, null=True)
    peso_embarque = models.CharField(blank=True, null=True)  

    # Quem cadastrou
    criado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="navios"
    )

    def __str__(self):
        return f"{self.armador or '---'} - {self.local_atracacao or '---'}"



class FotoVideoNavio(models.Model):
    navio = models.ForeignKey(Navio, on_delete=models.CASCADE, related_name="midias")
    arquivo = models.FileField(upload_to="navios/midias/")
    observacao = models.TextField(blank=True, null=True)
    tipo_peca = models.CharField(max_length=50, blank=True, null=True)  # Novo campo para tipo de peça
    data_criacao = models.DateTimeField(auto_now_add=True)

    def is_image(self):
        return self.arquivo.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))

    def is_video(self):
        return self.arquivo.name.lower().endswith(('.mp4', '.avi', '.mov'))
    
    
class DocumentoNavio(models.Model):
    navio = models.ForeignKey(Navio, on_delete=models.CASCADE, related_name="documentos")
    arquivo = models.FileField(upload_to="navios/documentos/")