from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from ..models import FotoVideoNavio, Navio
from ..permissions import filter_midia_queryset, filter_owned_queryset, profile_role


@login_required
def dashboard_view(request):
    navios = filter_owned_queryset(
        request.user, Navio.objects.select_related("criado_por")
    )
    midias_base = filter_midia_queryset(
        request.user,
        FotoVideoNavio.objects.select_related("navio", "navio__criado_por"),
    )

    total_navios = navios.count()
    hoje = timezone.now()
    trinta_dias_atras = hoje - timedelta(days=30)
    total_navios_30d = navios.filter(eta__gte=trinta_dias_atras, eta__lte=hoje).count()

    ultimos_navios = []
    for navio in navios.order_by("-id")[:5]:
        criador = navio.criado_por
        ultimos_navios.append(
            {
                "navio": navio,
                "criado_por_nome": _display_user(criador),
                "criado_por_perfil": profile_role(criador) if criador else "sem perfil",
            }
        )
    midias = (
        midias_base.filter(data_criacao__gte=trinta_dias_atras)
        .values("tipo_peca")
        .order_by("tipo_peca")
    )

    grafico_dados = {}
    for m in midias:
        tipo_raw = m["tipo_peca"] or "Não informado"
        tipo_norm = tipo_raw.strip().lower()
        grafico_dados[tipo_norm] = grafico_dados.get(tipo_norm, 0) + 1

    grafico_labels = [tipo.capitalize() for tipo in grafico_dados]
    grafico_values = list(grafico_dados.values())

    context = {
        "total_navios": total_navios,
        "total_navios_30d": total_navios_30d,
        "ultimos_navios": ultimos_navios,
        "grafico_labels": grafico_labels,
        "grafico_values": grafico_values,
    }

    return render(request, "historico/dashboard.html", context)


def _display_user(user):
    if not user:
        return "Nao informado"
    return user.get_full_name() or user.username
