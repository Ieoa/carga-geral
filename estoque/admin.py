from django.contrib import admin

from .models import Certificacao, Colaborador, Equipamento

admin.site.register(Colaborador)
admin.site.register(Equipamento)
admin.site.register(Certificacao)

