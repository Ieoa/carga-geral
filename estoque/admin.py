from django.contrib import admin

from .models import Certificacao, Colaborador, Equipamento, MovimentacaoMaterial

admin.site.register(Colaborador)
admin.site.register(Equipamento)
admin.site.register(Certificacao)
admin.site.register(MovimentacaoMaterial)

