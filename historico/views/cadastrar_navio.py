from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from ..audit import log_action, snapshot
from ..forms import DocumentoNavioForm, NavioForm
from ..models import DocumentoNavio, FotoVideoNavio
from ..uploads import collect_upload_errors


@login_required
def cadastrar_navio(request):
    if request.method == "POST":
        navio_form = NavioForm(request.POST)
        documento_form = DocumentoNavioForm(request.POST, request.FILES)

        midias_files = request.FILES.getlist("midias")
        arquivos_pdf = request.FILES.getlist("arquivos")
        observacoes = request.POST.getlist("observacoes")
        tipos_pecas = request.POST.getlist("tipo_peca")

        upload_errors = collect_upload_errors(documents=arquivos_pdf, media=midias_files)
        if navio_form.is_valid() and not upload_errors:
            with transaction.atomic():
                navio = navio_form.save(commit=False)
                navio.criado_por = request.user
                navio.atualizado_por = request.user
                navio.save()
                log_action(request.user, navio, "create", snapshot(navio))

                for arquivo in arquivos_pdf:
                    documento = DocumentoNavio.objects.create(
                        navio=navio,
                        arquivo=arquivo,
                        criado_por=request.user,
                    )
                    log_action(request.user, documento, "create", snapshot(documento))

                for idx, file in enumerate(midias_files):
                    obs = observacoes[idx] if idx < len(observacoes) else ""
                    tipo_peca = tipos_pecas[idx] if idx < len(tipos_pecas) else ""
                    midia = FotoVideoNavio.objects.create(
                        navio=navio,
                        arquivo=file,
                        observacao=obs,
                        tipo_peca=tipo_peca,
                        criado_por=request.user,
                    )
                    log_action(request.user, midia, "create", snapshot(midia))

            messages.success(request, "Navio cadastrado com sucesso!")
            return redirect(reverse("cadastrar_navio") + "?sucesso=true")

        for error in upload_errors:
            messages.error(request, error)
        messages.error(request, "Por favor, corrija os erros no formulário.")
    else:
        navio_form = NavioForm()
        documento_form = DocumentoNavioForm()

    return render(
        request,
        "historico/cadastro_navio.html",
        {
            "navio_form": navio_form,
            "documento_form": documento_form,
            "cadastro_sucesso": request.GET.get("sucesso", False),
        },
    )
