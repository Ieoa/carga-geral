from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..audit import log_action, snapshot
from ..models import Navio
from ..permissions import can_delete_records


@login_required
def excluir_navio(request, pk):
    navio = get_object_or_404(Navio, pk=pk)
    if not can_delete_records(request.user):
        messages.error(request, "Somente administradores e gestores podem excluir navios.")
        return redirect("pagina_pesquisa_midias")
    if request.method == "POST":
        before = snapshot(navio)
        log_action(request.user, navio, "delete", before)
        navio.delete()
        messages.success(request, "Navio e seus arquivos vinculados foram excluídos.")
        return redirect("pagina_pesquisa_midias")
    return render(request, "historico/excluir_navio.html", {"navio": navio})
