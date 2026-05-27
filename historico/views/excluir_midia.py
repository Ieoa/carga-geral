from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..audit import log_action, snapshot
from ..models import FotoVideoNavio
from ..permissions import can_delete_records


@login_required
def excluir_midia(request, pk):
    midia = get_object_or_404(FotoVideoNavio, pk=pk)
    if not can_delete_records(request.user):
        messages.error(request, "Somente administradores e gerentes podem excluir registros.")
        return redirect("pagina_pesquisa_midias")

    if request.method == "POST":
        before = snapshot(midia)
        log_action(request.user, midia, "delete", before)
        midia.delete()
        return redirect("pagina_pesquisa_midias")
    return render(request, "historico/excluir_midia.html", {"midia": midia})
