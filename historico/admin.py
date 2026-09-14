# admin.py
from django import forms
from django.contrib import admin

from .models import AuditLog, Colaborador


class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        exclude = ['user']  # Exclui o campo user do formulário

class ColaboradorAdmin(admin.ModelAdmin):
    form = ColaboradorForm
    readonly_fields = ['user']  # Exibe o user após salvar
    list_display = ['nome', 'sobrenome', 'matricula', 'cpf']

admin.site.register(Colaborador, ColaboradorAdmin)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "actor_role", "action", "app_label", "model_name", "object_repr"]
    list_filter = ["actor_role", "action", "app_label", "model_name", "created_at"]
    search_fields = ["object_repr", "object_pk", "user__username"]
    readonly_fields = ["created_at", "user", "actor_role", "action", "app_label", "model_name", "object_pk", "object_repr", "changes"]
