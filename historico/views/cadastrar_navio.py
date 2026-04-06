# Importações necessárias do Django
from django.shortcuts import render, redirect   # render: exibe o template | redirect: redireciona para outra URL
from django.contrib import messages             # usado para exibir mensagens de sucesso/erro no template
from django.contrib.auth.decorators import login_required  # força login para acessar essa view
from django.urls import reverse                 # gera URLs dinâmicas a partir do nome da rota
from ..forms import NavioForm, DocumentoNavioForm  # importa os formulários de navio e documentos
from ..models import Navio, DocumentoNavio, FotoVideoNavio  # importa os models usados

# 🔒 View só acessível para usuários logados
@login_required
def cadastrar_navio(request):
    # Se o usuário enviou o formulário (requisição POST)
    if request.method == "POST":
        # Preenche os formulários com os dados recebidos
        navio_form = NavioForm(request.POST)
        documento_form = DocumentoNavioForm(request.POST, request.FILES)

        # Captura listas de arquivos e campos extras
        midias_files = request.FILES.getlist('midias')     # imagens/vídeos
        arquivos_pdf = request.FILES.getlist('arquivos')   # PDFs
        observacoes = request.POST.getlist('observacoes')  # observações de cada mídia
        tipos_pecas = request.POST.getlist('tipo_peca')    # tipos de peça de cada mídia

        # Se o formulário principal (Navio) for válido
        if navio_form.is_valid():
            # Cria o objeto Navio sem salvar ainda no BD
            navio = navio_form.save(commit=False)
            navio.criado_por = request.user  # adiciona o usuário logado como criador
            navio.save()  # salva o navio no banco

            # Salva os documentos PDF associados ao navio
            for arquivo in arquivos_pdf:
                if arquivo.content_type == 'application/pdf':  # garante que é PDF
                    DocumentoNavio.objects.create(navio=navio, arquivo=arquivo)

            # Salva as mídias (foto/vídeo) com observação e tipo de peça
            for idx, file in enumerate(midias_files):
                obs = observacoes[idx] if idx < len(observacoes) else ""  # pega a observação correspondente
                tipo_peca = tipos_pecas[idx] if idx < len(tipos_pecas) else ""  # pega tipo de peça correspondente
                FotoVideoNavio.objects.create(
                    navio=navio,
                    arquivo=file,
                    observacao=obs,
                    tipo_peca=tipo_peca
                )

            # Exibe mensagem de sucesso
            messages.success(request, "Navio cadastrado com sucesso!")
            
            # 🔄 Redireciona para a mesma página (GET), limpando o formulário
            # evita reenvio de dados se o usuário atualizar a página
            return redirect(reverse('cadastrar_navio') + '?sucesso=true')
        
        else:
            # Se o formulário for inválido, exibe erro
            messages.error(request, "Por favor, corrija os erros no formulário.")
    
    else:
        # Caso seja uma requisição GET (primeira vez que acessa a página)
        navio_form = NavioForm()
        documento_form = DocumentoNavioForm()

    # Verifica se o usuário veio de um cadastro bem-sucedido (redirect GET)
    sucesso = request.GET.get('sucesso', False)
    
    # Renderiza o template com os formulários e o estado de sucesso
    return render(request, "historico/cadastro_navio.html", {
        "navio_form": navio_form,
        "documento_form": documento_form,
        "cadastro_sucesso": sucesso
    })
