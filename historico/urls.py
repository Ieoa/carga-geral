from django.urls import path
from .views import dashboard, login, cadastrar_navio, pesquisar_midias, excluir_midia, detalhes_midia, pdf_midia, editar_navio, cadastrar_colaborador

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", login.login_view, name="login"),
    path("logout/", login.logout_view, name="logout"),
    path("dashboard/", dashboard.dashboard_view, name="dashboard"),
    path("cadastrar_navio/", cadastrar_navio.cadastrar_navio, name="cadastrar_navio"),

    # Página HTML + endpoint JSON separados
    path("pesquisa_midias/", pesquisar_midias.pagina_pesquisa_midias, name="pagina_pesquisa_midias"),
    path("pesquisar_midias/", pesquisar_midias.pesquisar_midias, name="pesquisar_midias"),
    path("midia/<int:pk>/editar/", editar_navio.editar_navio, name="editar_navio_via_midia"),
    path("midia/<int:pk>/excluir/", excluir_midia.excluir_midia, name="excluir_midia"),
    path("midia/<int:pk>/visualizar/", detalhes_midia.visualizar_midia, name="visualizar_midia"),
    path("midia/<int:pk>/pdf/", pdf_midia.gerar_pdf_midia, name="gerar_pdf_midia"),
    path("colaboradores/cadastrar/", cadastrar_colaborador.cadastrar_colaborador, name="cadastrar_colaborador")
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    
    