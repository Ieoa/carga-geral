# seu_app/views.py

# Importa funções e classes essenciais do Django
from django.shortcuts import render, redirect   # render: renderiza templates | redirect: redireciona para outra rota
from django.contrib.auth.decorators import login_required  # login_required: obriga o usuário a estar logado para acessar a view
from django.contrib import messages  # messages: usado para exibir mensagens de sucesso/erro no template
from ..forms import ColaboradorForm  # importa o formulário personalizado do colaborador

# 🔒 A view só pode ser acessada por usuários autenticados
@login_required
def cadastrar_colaborador(request):
    # Verifica se o método da requisição é POST (quando o usuário clicou no "Salvar")
    if request.method == "POST":
        # Preenche o formulário com os dados enviados pelo usuário
        form = ColaboradorForm(request.POST)

        # Valida se os dados recebidos estão corretos (conforme regras do formulário/model)
        if form.is_valid():
            form.save()  # Salva o colaborador no banco de dados
            # Cria uma mensagem de sucesso que será exibida no template
            messages.success(request, "Colaborador cadastrado com sucesso!")
            
            # 🔄 Redireciona para a mesma view (mas com método GET),
            # isso evita que o formulário seja reenviado caso o usuário atualize a página.
            return redirect('cadastrar_colaborador')
        else:
            # Caso o formulário seja inválido, cria uma mensagem de erro
            # Os erros específicos também ficam disponíveis em "form.errors"
            messages.error(request, "Erro ao cadastrar. Por favor, verifique os campos e tente novamente.")
    else:
        # Caso a requisição seja GET (primeiro acesso ou após o redirect),
        # cria um formulário vazio para o usuário preencher
        form = ColaboradorForm()

    # Renderiza o template HTML, passando o formulário para ser exibido
    return render(request, "historico/cadastrar_colaborador.html", {"form": form})
