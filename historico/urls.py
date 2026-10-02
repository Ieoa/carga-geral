from django.urls import path

from .views import (
    auditoria,
    cadastrar_colaborador,
    cadastrar_navio,
    dashboard,
    detalhes_midia,
    editar_navio,
    excluir_midia,
    excluir_navio,
    insight,
    login,
    pdf_midia,
    pesquisar_midias,
)
from .views.password import RequiredPasswordChangeView

urlpatterns = [
    path("", login.login_view, name="login"),
    path("logout/", login.logout_view, name="logout"),
    path("alterar-senha/", RequiredPasswordChangeView.as_view(), name="alterar_senha"),
    path("dashboard/", dashboard.dashboard_view, name="dashboard"),
    path("cadastrar_navio/", cadastrar_navio.cadastrar_navio, name="cadastrar_navio"),

    # Página HTML + endpoint JSON separados
    path("pesquisa_midias/", pesquisar_midias.pagina_pesquisa_midias, name="pagina_pesquisa_midias"),
    path("pesquisar_midias/", pesquisar_midias.pesquisar_midias, name="pesquisar_midias"),
    path("midia/<int:pk>/editar/", editar_navio.editar_navio, name="editar_navio_via_midia"),
    path("navio/<int:pk>/editar/", editar_navio.editar_navio_direto, name="editar_navio"),
    path("midia/<int:pk>/excluir/", excluir_midia.excluir_midia, name="excluir_midia"),
    path("navio/<int:pk>/excluir/", excluir_navio.excluir_navio, name="excluir_navio"),
    path("midia/<int:pk>/visualizar/", detalhes_midia.visualizar_midia, name="visualizar_midia"),
    path("midia/<int:pk>/pdf/", pdf_midia.gerar_pdf_midia, name="gerar_pdf_midia"),
    path("auditoria/", auditoria.auditoria, name="auditoria"),
    path("insight/", insight.insight_dashboard, name="insight_dashboard"),
    path("insight/api/navios/<int:pk>/", insight.insight_navio_api, name="insight_navio_api"),
    path("colaboradores/cadastrar/", cadastrar_colaborador.cadastrar_colaborador, name="cadastrar_colaborador")
]
    
    
    
