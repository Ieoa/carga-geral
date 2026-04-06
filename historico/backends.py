# historico/backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from .models import Colaborador

class MatriculaCPFBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Tenta encontrar o Colaborador pela matrícula (username)
            colaborador = Colaborador.objects.get(matricula=username)
            # Limpa o CPF (remove pontos e traço) e pega os 6 primeiros dígitos
            cpf_limpo = ''.join(filter(str.isdigit, colaborador.cpf))
            senha_correta = cpf_limpo[:6]
            
            # Verifica se a senha fornecida corresponde aos 6 primeiros dígitos do CPF
            if password == senha_correta:
                return colaborador.user
        except Colaborador.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None