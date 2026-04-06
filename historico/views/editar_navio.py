from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..forms import NavioForm, DocumentoNavioForm, FotoVideoNavioForm
from ..models import Navio, DocumentoNavio, FotoVideoNavio


@login_required
def editar_navio(request, pk):
    navio = get_object_or_404(Navio, pk=pk)
    documentos = DocumentoNavio.objects.filter(navio=navio)
    midias = FotoVideoNavio.objects.filter(navio=navio)

    if request.method == "POST":
        navio_form = NavioForm(request.POST, instance=navio)
        arquivos_pdf = request.FILES.getlist("arquivos")
        midias_files = request.FILES.getlist("midias")
        observacoes = request.POST.getlist("observacoes")
        tipo_pecas = request.POST.getlist("tipo_peca")

        if navio_form.is_valid():
            navio = navio_form.save()

            # salvar novos PDFs
            for arquivo in arquivos_pdf:
                if arquivo.content_type == "application/pdf":
                    DocumentoNavio.objects.create(navio=navio, arquivo=arquivo)

            # salvar novas mídias
            for idx, file in enumerate(midias_files):
                obs = observacoes[idx] if idx < len(observacoes) else ""
                tipo = tipo_pecas[idx] if idx < len(tipo_pecas) else ""
                FotoVideoNavio.objects.create(
                    navio=navio, arquivo=file, observacao=obs, tipo_peca=tipo
                )

            messages.success(request, "Navio atualizado com sucesso.")
            return redirect('pagina_pesquisa_midias')

        else:
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
