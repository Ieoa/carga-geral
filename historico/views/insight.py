from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import render

from ..models import Navio
from ..permissions import filter_owned_queryset
from ..services.insight import analyze_navios


def _visible_navios(user):
    return list(filter_owned_queryset(user, Navio.objects.order_by("pk")))


@login_required
def insight_dashboard(request):
    analysis = analyze_navios(_visible_navios(request.user))
    results = analysis["resultados"]

    risk = request.GET.get("risco", "").strip().lower()
    query = request.GET.get("q", "").strip().lower()
    if risk in {"alto", "medio", "baixo"}:
        results = [item for item in results if item["risco"] == risk]
    else:
        risk = ""
    if query:
        results = [
            item for item in results
            if query in item["navio"].lower()
            or query in item["armador"].lower()
            or query in item["agencia"].lower()
        ]

    visible_summary = {
        "total": len(results),
        "alto": sum(item["risco"] == "alto" for item in results),
        "medio": sum(item["risco"] == "medio" for item in results),
        "baixo": sum(item["risco"] == "baixo" for item in results),
    }
    paginator = Paginator(results, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "historico/insight.html", {
        "page_obj": page_obj,
        "resumo": visible_summary,
        "modelo": analysis["modelo"],
        "risco": risk,
        "busca": request.GET.get("q", "").strip(),
    })


@login_required
def insight_navio_api(request, pk):
    navios = _visible_navios(request.user)
    if not any(navio.pk == pk for navio in navios):
        raise Http404
    analysis = analyze_navios(navios)
    result = next((item for item in analysis["resultados"] if item["navio_id"] == pk), None)
    if result is None:
        raise Http404
    return JsonResponse(
        {"analise": result, "modelo": analysis["modelo"]},
        json_dumps_params={"ensure_ascii": False},
    )
