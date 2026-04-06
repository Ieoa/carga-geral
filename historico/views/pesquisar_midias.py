from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from ..models import FotoVideoNavio
from datetime import datetime

@login_required
def pagina_pesquisa_midias(request):
    """Renderiza a página de pesquisa de mídias"""
    return render(request, "historico/pesquisa_midias.html")



@login_required
def pesquisar_midias(request):
    query = request.GET.get("q", "").strip()
    resultados = FotoVideoNavio.objects.select_related("navio")

    if query:
        filtros = (
            Q(tipo_peca__icontains=query) |
            Q(observacao__icontains=query) |
            Q(navio__navio__icontains=query) |
            Q(navio__agencia__icontains=query) |   # 👈 novo campo
            Q(navio__armador__icontains=query)     # 👈 novo campo
        )

        # 👇 tentativa de interpretar como data
        try:
            data_formatada = datetime.strptime(query, "%d/%m/%Y").date()
            filtros |= (
                Q(navio__inicio_operacao__date=data_formatada) |
                Q(navio__fim_operacao__date=data_formatada)
            )
        except ValueError:
            pass

        resultados = resultados.filter(filtros).order_by("-data_criacao")
    else:
        resultados = resultados.order_by("-data_criacao")

    data = []
    for midia in resultados:
        data.append({
            "id": midia.id,
            "arquivo": midia.arquivo.url,
            "is_image": midia.is_image(),
            "is_video": midia.is_video(),
            "tipo_peca": midia.tipo_peca,
            "navio": midia.navio.navio,
            "navio_id": midia.navio.id,
            "agencia": getattr(midia.navio, "agencia", "---"),   # 👈 envia p/ frontend
            "armador": getattr(midia.navio, "armador", "---"),
            "inicio": midia.navio.inicio_operacao.strftime("%d/%m/%Y %H:%M") if midia.navio.inicio_operacao else None,
            "fim": midia.navio.fim_operacao.strftime("%d/%m/%Y %H:%M") if midia.navio.fim_operacao else None,
        })

    return JsonResponse({"resultados": data})