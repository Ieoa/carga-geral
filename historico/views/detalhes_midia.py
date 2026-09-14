from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import FotoVideoNavio, DocumentoNavio
from ..permissions import profile_role

### Esse módulo faz a renderização da visualização de uma mídia específica 
### (foto ou vídeo) vinculada a um navio, junto com seus documentos associados.

@login_required
def visualizar_midia(request, pk):
    """
    View responsável por exibir os detalhes de uma mídia (foto ou vídeo) 
    associada a um navio, bem como os documentos relacionados a esse mesmo navio.

    Args:
        request: Objeto HttpRequest que contém dados da requisição.
        pk (int): Chave primária da mídia (FotoVideoNavio) a ser exibida.

    Returns:
        HttpResponse: Renderiza o template 'historico/visualizar_midia.html'
        com os dados da mídia e dos documentos associados.
    """
    # Busca a mídia pelo ID ou retorna 404 se não existir
    midia = get_object_or_404(FotoVideoNavio.objects.select_related("navio", "navio__criado_por"), pk=pk)
    
    # Pega todos os documentos vinculados ao navio dessa mídia
    documentos = DocumentoNavio.objects.filter(navio=midia.navio)
    
    # Renderiza o template com os dados
    criador = midia.navio.criado_por
    return render(request, "historico/visualizar_midia.html", {
        "midia": midia,
        "documentos": documentos,
        "cadastrado_por": _display_user(criador),
        "perfil_cadastro": profile_role(criador) if criador else "sem perfil",
    })


def _display_user(user):
    if not user:
        return "Nao informado"
    return user.get_full_name() or user.username
