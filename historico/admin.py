# admin.py
from django import forms
from django.contrib import admin
from .models import Colaborador

class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        exclude = ['user']  # Exclui o campo user do formulário

class ColaboradorAdmin(admin.ModelAdmin):
    form = ColaboradorForm
    readonly_fields = ['user']  # Exibe o user após salvar
    list_display = ['nome', 'sobrenome', 'matricula', 'cpf']

admin.site.register(Colaborador, ColaboradorAdmin)