from datetime import date, datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from ..models import FotoVideoNavio
from ..permissions import (
    can_delete_records,
    can_edit_object,
    filter_midia_queryset,
    profile_role,
)


@login_required
def pagina_pesquisa_midias(request):
    """Renderiza a página de pesquisa de mídias"""
    return render(request, "historico/pesquisa_midias.html")


@login_required
def pesquisar_midias(request):
    query = request.GET.get("q", "").strip()
    resultados = filter_midia_queryset(
        request.user,
        FotoVideoNavio.objects.select_related("navio", "navio__criado_por"),
    )

    if query:
        filtros = (
            Q(tipo_peca__icontains=query)
            | Q(observacao__icontains=query)
            | Q(navio__navio__icontains=query)
            | Q(navio__agencia__icontains=query)
            | Q(navio__armador__icontains=query)
        )

        try:
            dia, mes, ano = (int(parte) for parte in query.split("/"))
            data_formatada = date(ano, mes, dia)
            inicio_dia = timezone.make_aware(datetime.combine(data_formatada, time.min))
            fim_dia = inicio_dia + timedelta(days=1)
            filtros |= Q(
                navio__inicio_operacao__gte=inicio_dia,
                navio__inicio_operacao__lt=fim_dia,
            ) | Q(navio__fim_operacao__gte=inicio_dia, navio__fim_operacao__lt=fim_dia)
        except ValueError:
            pass

        resultados = resultados.filter(filtros).order_by("-data_criacao")
    else:
        resultados = resultados.order_by("-data_criacao")

    paginator = Paginator(resultados, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    data = []
    for midia in page_obj:
        criador = midia.navio.criado_por
        data.append(
            {
                "id": midia.id,
                "arquivo": midia.arquivo.url,
                "is_image": midia.is_image(),
                "is_video": midia.is_video(),
                "tipo_peca": midia.tipo_peca,
                "navio": midia.navio.navio,
                "navio_id": midia.navio.id,
                "agencia": getattr(midia.navio, "agencia", "---"),
                "armador": getattr(midia.navio, "armador", "---"),
                "inicio": midia.navio.inicio_operacao.strftime("%d/%m/%Y %H:%M")
                if midia.navio.inicio_operacao
                else None,
                "fim": midia.navio.fim_operacao.strftime("%d/%m/%Y %H:%M")
                if midia.navio.fim_operacao
                else None,
                "cadastrado_por": _display_user(criador),
                "perfil_cadastro": profile_role(criador) if criador else "sem perfil",
                "can_edit": can_edit_object(request.user, midia.navio),
                "can_delete": can_delete_records(request.user),
            }
        )

    return JsonResponse(
        {
            "resultados": data,
            "paginacao": {
                "pagina": page_obj.number,
                "total_paginas": paginator.num_pages,
                "tem_proxima": page_obj.has_next(),
            },
        }
    )


def _display_user(user):
    if not user:
        return "Nao informado"
    return user.get_full_name() or user.username
