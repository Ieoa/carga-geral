from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from ..audit import diff, log_action, snapshot
from ..forms import NavioForm
from ..models import DocumentoNavio, FotoVideoNavio, Navio
from ..permissions import can_edit_object
from ..uploads import collect_upload_errors


@login_required
def editar_navio(request, pk):
    midia_or_navio = (
        FotoVideoNavio.objects.select_related("navio").filter(pk=pk).first()
    )
    navio = midia_or_navio.navio if midia_or_navio else get_object_or_404(Navio, pk=pk)
    if not can_edit_object(request.user, navio):
        messages.error(request, "Você só pode alterar navios cadastrados por você.")
        return redirect("pagina_pesquisa_midias")

    documentos = DocumentoNavio.objects.filter(navio=navio)
    midias = FotoVideoNavio.objects.filter(navio=navio)

    if request.method == "POST":
        before = snapshot(navio)
        navio_form = NavioForm(request.POST, instance=navio)
        arquivos_pdf = request.FILES.getlist("arquivos")
        midias_files = request.FILES.getlist("midias")
        observacoes = request.POST.getlist("observacoes")
        tipo_pecas = request.POST.getlist("tipo_peca")

        upload_errors = collect_upload_errors(
            documents=arquivos_pdf, media=midias_files
        )
        if navio_form.is_valid() and not upload_errors:
            with transaction.atomic():
                navio = navio_form.save(commit=False)
                navio.atualizado_por = request.user
                navio.save()

                changes = diff(before, snapshot(navio))
                if changes:
                    log_action(request.user, navio, "update", changes)

                for arquivo in arquivos_pdf:
                    documento = DocumentoNavio.objects.create(
                        navio=navio,
                        arquivo=arquivo,
                        criado_por=request.user,
                    )
                    log_action(request.user, documento, "create", snapshot(documento))

                for idx, file in enumerate(midias_files):
                    obs = observacoes[idx] if idx < len(observacoes) else ""
                    tipo = tipo_pecas[idx] if idx < len(tipo_pecas) else ""
                    midia = FotoVideoNavio.objects.create(
                        navio=navio,
                        arquivo=file,
                        observacao=obs,
                        tipo_peca=tipo,
                        criado_por=request.user,
                    )
                    log_action(request.user, midia, "create", snapshot(midia))

            messages.success(request, "Navio atualizado com sucesso.")
            return redirect("pagina_pesquisa_midias")

        for error in upload_errors:
            messages.error(request, error)
        messages.error(request, "Corrija os erros no formulário.")
    else:
        navio_form = NavioForm(instance=navio)

    return render(
        request,
        "historico/editar_navio.html",
        {
            "navio_form": navio_form,
            "navio": navio,
            "documentos": documentos,
            "midias": midias,
        },
    )
