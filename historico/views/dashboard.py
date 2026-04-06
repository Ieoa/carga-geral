from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from ..models import Navio, FotoVideoNavio
from django.contrib.auth.decorators import login_required
#from ..utils.scraping_praticagem_reduzido import get_navios_cargo_reduzido

@login_required
def dashboard_view(request):
    # Total de navios
    total_navios = Navio.objects.count()
    #navios_praticagem = get_navios_cargo_reduzido()
    # Total de navios nos últimos 30 dias
    hoje = timezone.now()
    trinta_dias_atras = hoje - timedelta(days=30)
    total_navios_30d = Navio.objects.filter(criado_por__isnull=False, eta__gte=trinta_dias_atras).count()

    # Últimos 5 navios cadastrados
    ultimos_navios = Navio.objects.order_by("-id")[:5]
    # Gráfico de materiais por tipo (últimos 30 dias)
    midias = (
        FotoVideoNavio.objects
        .filter(data_criacao__gte=trinta_dias_atras)
        .values("tipo_peca")
        .order_by("tipo_peca")
    )

    grafico_dados = {}
    for m in midias:
        tipo_raw = m["tipo_peca"] or "Não informado"
        tipo_norm = tipo_raw.strip().lower()  # normaliza para evitar duplicação
        grafico_dados[tipo_norm] = grafico_dados.get(tipo_norm, 0) + 1

    # Ajuste final: colocar primeira letra maiúscula na label
    grafico_labels = [tipo.capitalize() for tipo in grafico_dados.keys()]
    grafico_values = list(grafico_dados.values())

    context = {
        "total_navios": total_navios,
        "total_navios_30d": total_navios_30d,
        "ultimos_navios": ultimos_navios,
        "grafico_labels": grafico_labels,
        "grafico_values": grafico_values,
        #"navios_praticagem": navios_praticagem,
    }


    return render(request, "historico/dashboard.html", context)
