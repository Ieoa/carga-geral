from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path

from historico.views.health import health_check
from historico.views.media import protected_media

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("", include("historico.urls")),  # inclui suas rotas do app
    path("estoque/", include(("estoque.urls", "estoque"), namespace="estoque")),
]

urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        protected_media,
        name="protected_media",
    )
]

# Handler de erro personalizado
def custom_page_not_found(request, exception):
    return render(request, "historico/404.html", status=404
                  )
    
def custom_server_error(request):
    return render(request, "historico/404.html", status=500)


handler404 = custom_page_not_found
