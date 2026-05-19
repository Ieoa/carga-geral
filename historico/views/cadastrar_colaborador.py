from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def cadastrar_colaborador(request):
    return redirect("estoque:cadastrar_colaborador")
