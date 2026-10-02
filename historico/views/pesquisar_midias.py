from datetime import date, datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..models import Navio
from ..permissions import (
    can_delete_records,
    can_edit_object,
    filter_owned_queryset,
    profile_role,
)


@login_required
def pagina_pesquisa_midias(request):
    """Renderiza a página de pesquisa de mídias"""
    return render(request, "historico/pesquisa_midias.html")


@login_required
def pesquisar_midias(request):
    query = request.GET.get("q", "").strip()
    data_inicio = _parse_iso_date(request.GET.get("data_inicio", ""))
    data_fim = _parse_iso_date(request.GET.get("data_fim", ""))
    periodo_texto = _parse_month_query(query)
    if periodo_texto:
        data_inicio, data_fim = periodo_texto
        query = ""
    resultados = filter_owned_queryset(
        request.user,
        Navio.objects.select_related("criado_por").prefetch_related("midias"),
    )

    if data_inicio:
        inicio_periodo = timezone.make_aware(datetime.combine(data_inicio, time.min))
        resultados = resultados.filter(inicio_operacao__gte=inicio_periodo)
    if data_fim:
        fim_periodo = timezone.make_aware(
            datetime.combine(data_fim + timedelta(days=1), time.min)
        )
        resultados = resultados.filter(inicio_operacao__lt=fim_periodo)

    if query:
        filtros = (
            Q(midias__tipo_peca__icontains=query)
            | Q(midias__observacao__icontains=query)
            | Q(navio__icontains=query)
            | Q(agencia__icontains=query)
            | Q(armador__icontains=query)
        )

        try:
            dia, mes, ano = (int(parte) for parte in query.split("/"))
            data_formatada = date(ano, mes, dia)
            inicio_dia = timezone.make_aware(datetime.combine(data_formatada, time.min))
            fim_dia = inicio_dia + timedelta(days=1)
            filtros |= Q(
                inicio_operacao__gte=inicio_dia,
                inicio_operacao__lt=fim_dia,
            ) | Q(fim_operacao__gte=inicio_dia, fim_operacao__lt=fim_dia)
        except ValueError:
            pass

        resultados = resultados.filter(filtros).distinct().order_by(
            "-inicio_operacao", "-pk"
        )
    else:
        resultados = resultados.order_by("-inicio_operacao", "-pk")

    paginator = Paginator(resultados, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    data = []
    for navio in page_obj:
        midia = next(iter(navio.midias.all()), None)
        criador = navio.criado_por
        data.append(
            {
                "id": midia.id if midia else None,
                "arquivo": midia.arquivo.url if midia else None,
                "is_image": midia.is_image() if midia else False,
                "is_video": midia.is_video() if midia else False,
                "tipo_peca": midia.tipo_peca if midia else None,
                "navio": navio.navio,
                "navio_id": navio.id,
                "agencia": navio.agencia or "---",
                "armador": navio.armador or "---",
                "inicio": navio.inicio_operacao.strftime("%d/%m/%Y %H:%M")
                if navio.inicio_operacao
                else None,
                "fim": navio.fim_operacao.strftime("%d/%m/%Y %H:%M")
                if navio.fim_operacao
                else None,
                "cadastrado_por": _display_user(criador),
                "perfil_cadastro": profile_role(criador) if criador else "sem perfil",
                "can_edit": can_edit_object(request.user, navio),
                "can_delete": can_delete_records(request.user),
                "view_url": (
                    reverse("visualizar_midia", args=[midia.pk]) if midia else None
                ),
                "edit_url": reverse("editar_navio", args=[navio.pk]),
                "delete_url": reverse("excluir_navio", args=[navio.pk]),
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


def _parse_iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_month_query(value):
    months = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }
    partes = value.lower().replace(" de ", " ").split()
    if len(partes) != 2 or partes[0] not in months:
        return None
    try:
        ano = int(partes[1])
        inicio = date(ano, months[partes[0]], 1)
    except ValueError:
        return None
    if inicio.month == 12:
        proximo = date(inicio.year + 1, 1, 1)
    else:
        proximo = date(inicio.year, inicio.month + 1, 1)
    return inicio, proximo - timedelta(days=1)
