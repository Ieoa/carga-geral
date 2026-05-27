from django.shortcuts import redirect

from ..permissions import can_manage_users, permission_required


@permission_required(can_manage_users, "Somente administradores podem cadastrar usuários.")
def cadastrar_colaborador(request):
    return redirect("estoque:cadastrar_colaborador")
