from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from ..models import FotoVideoNavio



@login_required
def excluir_midia(request, pk):
    midia = get_object_or_404(FotoVideoNavio, pk=pk)
    if request.method == "POST":
        midia.delete()
        return redirect("pagina_pesquisa_midias")
    return render(request, "historico/excluir_midia.html", {"midia": midia})
