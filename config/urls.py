from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("historico.urls")),  # inclui suas rotas do app
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Handler de erro personalizado
def custom_page_not_found(request, exception):
    return render(request, "historico/404.html", status=404
                  )
    
def custom_server_error(request):
    return render(request, "historico/404.html", status=500)


handler404 = custom_page_not_found
