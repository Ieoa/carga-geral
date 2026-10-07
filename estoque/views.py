"""
Views para sistema de estoque com autenticação e CRUD para colaboradores e equipamentos.
Organizado seguindo boas práticas Pythonicas com imports agrupados e comentários descritivos.
"""

import logging

# Django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from historico.audit import diff, log_action, snapshot
from historico.permissions import (
    can_delete_records,
    can_edit_object,
    can_manage_users,
    filter_owned_queryset,
    is_manager,
    profile_role,
)
from historico.security import (
    authorize_user_for_ad,
    create_pre_authorized_ad_user,
    create_user_with_temporary_password,
)

# Local Apps
from .forms import (
    CertificacaoEdicaoForm,
    CertificacaoRenovacaoForm,
    ColaboradorForm,
    EquipamentoForm,
    MovimentacaoMaterialForm,
)
from .models import Certificacao, Colaborador, Equipamento, MovimentacaoMaterial
from .services.certificacoes import (
    certificados_para_notificar,
    email_delivery_status,
    enviar_avisos_certificados,
)
from .services.certificate_payloads import parse_certificate_payloads
from .services.email_recipients import normalize_email_recipients

logger = logging.getLogger(__name__)


def estoque_entry(request):
    """Mantém a URL histórica do estoque usando o login único do LOGGERAL."""
    if request.user.is_authenticated:
        return redirect("estoque:dashboard")
    return redirect(f"{reverse('login')}?next={reverse('estoque:dashboard')}")


@login_required
def dashboard(request):
    """Página inicial após login"""
    return render(request, "estoque/dashboard.html")


# ==============================================
# VIEWS PARA GESTÃO DE COLABORADORES
# ==============================================


@login_required
def cadastrar_colaborador(request):
    """
    Cadastra novo colaborador e cria usuário associado.
    Requer permissões de superusuário ou 'estoque.add_colaborador'.
    """
    # Verificação de permissões
    if not can_manage_users(request.user):
        messages.error(request, "Somente administradores podem cadastrar usuários.")
        return redirect("estoque:dashboard")

    if request.method == "POST":
        form = ColaboradorForm(request.POST)
        if form.is_valid():
            try:
                colaborador = form.save(commit=False)
                nomes = colaborador.nome.strip().split()

                with transaction.atomic():
                    user = User.objects.filter(
                        username__iexact=colaborador.matricula
                    ).first()
                    temporary_password = None
                    if user is None:
                        user_data = {
                            "username": colaborador.matricula,
                            "first_name": nomes[0],
                            "last_name": " ".join(nomes[1:]) if len(nomes) > 1 else "",
                        }
                        if settings.AD_AUTH_ENABLED:
                            user = create_pre_authorized_ad_user(**user_data)
                        else:
                            user, temporary_password = create_user_with_temporary_password(
                                **user_data,
                            )
                    else:
                        user.first_name = nomes[0]
                        user.last_name = " ".join(nomes[1:]) if len(nomes) > 1 else ""
                        user.email = ""
                        user.save(update_fields=["email", "first_name", "last_name"])
                        if settings.AD_AUTH_ENABLED:
                            authorize_user_for_ad(user)

                    colaborador.user = user
                    colaborador.data_criacao = timezone.now()
                    colaborador.save()
                    log_action(
                        request.user, colaborador, "create", snapshot(colaborador)
                    )

                if temporary_password:
                    messages.success(
                        request,
                        f"Colaborador cadastrado. Senha temporária: {temporary_password} "
                        "(ela será exibida somente agora e deverá ser alterada no primeiro acesso).",
                    )
                else:
                    messages.success(
                        request,
                        "Usuário autorizado localmente para entrar com a conta corporativa.",
                    )
                return redirect("estoque:cadastrar_colaborador")

            except Exception:
                logger.exception("Falha ao cadastrar colaborador no estoque.")
                messages.error(
                    request,
                    "Não foi possível cadastrar o colaborador. Tente novamente ou consulte o suporte.",
                )
    else:
        form = ColaboradorForm()

    return render(
        request,
        "estoque/cadastro_colaborador.html",
        {
            "colaborador_form": form,
            "ad_enabled": settings.AD_AUTH_ENABLED,
        },
    )


@login_required
def listar_colaboradores(request):
    """Lista todas as contas autorizadas localmente, inclusive administradores."""
    if not can_manage_users(request.user):
        messages.error(request, "Somente administradores podem acessar colaboradores.")
        return redirect("estoque:dashboard")
    users = (
        User.objects.filter(access_control__isnull=False)
        .select_related("access_control", "estoque_colaborador")
        .order_by("username")
    )
    usuarios = []
    for user in users:
        try:
            colaborador = user.estoque_colaborador
        except Colaborador.DoesNotExist:
            colaborador = None
        usuarios.append(
            {
                "user": user,
                "colaborador": colaborador,
                "perfil": profile_role(user),
                "autenticacao": (
                    "Active Directory"
                    if settings.AD_AUTH_ENABLED or not user.has_usable_password()
                    else "Local"
                ),
            }
        )
    return render(
        request, "estoque/colaboradores.html", {"usuarios": usuarios}
    )


@login_required
def editar_colaborador(request, pk):
    """Edita informações de um colaborador existente"""
    if not can_manage_users(request.user):
        messages.error(request, "Somente administradores podem editar colaboradores.")
        return redirect("estoque:dashboard")
    colaborador = get_object_or_404(Colaborador, pk=pk)

    if request.method == "POST":
        before = snapshot(colaborador)
        form = ColaboradorForm(request.POST, instance=colaborador)
        if form.is_valid():
            with transaction.atomic():
                colaborador = form.save()
                colaborador.user.username = colaborador.matricula
                colaborador.user.first_name = colaborador.nome.split()[0]
                colaborador.user.last_name = " ".join(colaborador.nome.split()[1:])
                colaborador.user.save(
                    update_fields=["username", "first_name", "last_name"]
                )
                changes = diff(before, snapshot(colaborador))
                if changes:
                    log_action(request.user, colaborador, "update", changes)

            messages.success(request, "Colaborador atualizado com sucesso!")
            return redirect("estoque:listar_colaboradores")
    else:
        form = ColaboradorForm(instance=colaborador)

    return render(
        request,
        "estoque/editar_colaborador.html",
        {"form": form, "colaborador": colaborador},
    )


@login_required
def excluir_colaborador(request, pk):
    """Remove colaborador e usuário associado"""
    if not can_manage_users(request.user):
        messages.error(request, "Somente administradores podem excluir colaboradores.")
        return redirect("estoque:dashboard")
    colaborador = get_object_or_404(Colaborador, pk=pk)

    if request.method == "POST":
        before = snapshot(colaborador)
        log_action(request.user, colaborador, "delete", before)
        if colaborador.user:
            colaborador.user.delete()  # Remove usuário vinculado
        colaborador.delete()
        messages.success(request, "Colaborador excluído com sucesso!")
        return redirect("estoque:listar_colaboradores")

    return render(
        request, "estoque/excluir_colaborador.html", {"colaborador": colaborador}
    )


# ==============================================
# VIEWS PARA GESTÃO DE EQUIPAMENTOS
# ==============================================


@login_required
def cadastrar_equipamento(request):
    """Cadastra novo equipamento com certificados associados"""
    if request.method == "POST":
        form = EquipamentoForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                certificados_data = parse_certificate_payloads(request)
            except ValidationError as exc:
                for error in exc.messages:
                    form.add_error(None, error)
                return render(
                    request, "estoque/equipamento_cadastro.html", {"form": form}
                )

            with transaction.atomic():
                equipamento = form.save(commit=False)
                equipamento.criado_por = request.user
                equipamento.atualizado_por = request.user
                equipamento.save()
                log_action(request.user, equipamento, "create", snapshot(equipamento))

                for cert_data in certificados_data:
                    certificacao = Certificacao.objects.create(
                        equipamento=equipamento,
                        criado_por=request.user,
                        **cert_data,
                    )
                    log_action(
                        request.user, certificacao, "create", snapshot(certificacao)
                    )

            messages.success(request, "Equipamento cadastrado com sucesso!")
            return render(
                request,
                "estoque/equipamento_cadastro.html",
                {
                    "form": EquipamentoForm(),
                    "qr_code": equipamento.qrcode.url,
                    "exibir_modal": True,
                },
            )
        else:
            return render(request, "estoque/equipamento_cadastro.html", {"form": form})
    else:
        form = EquipamentoForm()

    return render(request, "estoque/equipamento_cadastro.html", {"form": form})


@login_required
def listar_equipamentos(request):
    """Lista equipamentos com possibilidade de busca"""
    busca = request.GET.get("q", "")
    equipamentos = Equipamento.objects.all()

    if busca:
        equipamentos = equipamentos.filter(
            Q(equipamento__icontains=busca)
            | Q(identificador__icontains=busca)
            | Q(registro__icontains=busca)
        )

    return render(
        request,
        "estoque/equipamento_lista.html",
        {"equipamentos": equipamentos, "busca": busca},
    )


@login_required
def detalhe_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    today = timezone.now().date()
    certificacao_principal = (
        equipamento.certificacoes.filter(ativa=True)
        .exclude(anexo="")
        .order_by("-data_certificacao", "-pk")
        .first()
    )
    return render(
        request,
        "estoque/equipamento_detalhe.html",
        {
            "equipamento": equipamento,
            "today": today,
            "certificacao_principal": certificacao_principal,
            "movimentacoes": equipamento.movimentacoes.select_related(
                "atualizado_por"
            )[:10],
            "can_edit": can_edit_object(request.user, equipamento),
            "can_delete": can_delete_records(request.user),
            "can_manage_movements": is_manager(request.user),
        },
    )


@login_required
def destino_qrcode(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    certificacao = (
        equipamento.certificacoes.filter(ativa=True)
        .exclude(anexo="")
        .order_by("-data_certificacao", "-pk")
        .first()
    )
    if certificacao:
        return redirect(certificacao.anexo.url)
    messages.info(request, "Este material ainda não possui PDF cadastrado.")
    return redirect("estoque:detalhe_equipamento", pk=equipamento.pk)


@login_required
def editar_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    if not can_edit_object(request.user, equipamento):
        messages.error(request, "Você só pode alterar materiais cadastrados por você.")
        return redirect("estoque:detalhe_equipamento", pk=equipamento.pk)

    before = snapshot(equipamento)
    form = EquipamentoForm(
        request.POST or None,
        request.FILES or None,
        instance=equipamento,
    )
    if request.method == "POST" and form.is_valid():
        equipamento = form.save(commit=False)
        equipamento.atualizado_por = request.user
        equipamento.save()
        changes = diff(before, snapshot(equipamento))
        if changes:
            log_action(request.user, equipamento, "update", changes)
        messages.success(request, "Material atualizado com sucesso.")
        return redirect("estoque:detalhe_equipamento", pk=equipamento.pk)

    return render(
        request,
        "estoque/equipamento_form.html",
        {"form": form, "equipamento": equipamento},
    )


@login_required
def excluir_equipamento(request, pk):
    equipamento = get_object_or_404(Equipamento, pk=pk)
    if not can_delete_records(request.user):
        messages.error(request, "Somente administradores e gestores podem excluir materiais.")
        return redirect("estoque:detalhe_equipamento", pk=equipamento.pk)
    if request.method == "POST":
        before = snapshot(equipamento)
        try:
            with transaction.atomic():
                log_action(request.user, equipamento, "delete", before)
                equipamento.delete()
        except ProtectedError:
            messages.error(
                request,
                "O material possui empréstimos registrados e não pode ser excluído. Desative-o ou preserve o histórico.",
            )
            return redirect("estoque:detalhe_equipamento", pk=pk)
        messages.success(request, "Material excluído com sucesso.")
        return redirect("estoque:listar_equipamentos")
    return render(
        request,
        "estoque/equipamento_confirmar_exclusao.html",
        {"equipamento": equipamento},
    )


def _salvar_movimentacao(form, user):
    """Salva um empréstimo sem permitir retirar mais unidades que o estoque."""
    equipamento_id = form.cleaned_data["equipamento"].pk
    with transaction.atomic():
        equipamento = Equipamento.objects.select_for_update().get(pk=equipamento_id)
        emprestados = (
            MovimentacaoMaterial.objects.filter(
                equipamento=equipamento,
                data_devolucao__isnull=True,
            )
            .exclude(pk=form.instance.pk)
            .aggregate(total=Sum("quantidade"))["total"]
            or 0
        )
        quantidade_nova = (
            form.cleaned_data["quantidade"]
            if form.cleaned_data.get("data_devolucao") is None
            else 0
        )
        disponiveis = max(equipamento.quantidade - emprestados, 0)
        if quantidade_nova > disponiveis:
            form.add_error(
                "quantidade",
                f"Há somente {disponiveis} unidade(s) disponível(is) para retirada.",
            )
            return None

        movimentacao = form.save(commit=False)
        movimentacao.equipamento = equipamento
        if not movimentacao.pk:
            movimentacao.criado_por = user
        movimentacao.atualizado_por = user
        movimentacao.save()
        return movimentacao


@login_required
def listar_movimentacoes(request):
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    movimentacoes = MovimentacaoMaterial.objects.select_related(
        "equipamento", "criado_por", "atualizado_por"
    )
    if busca:
        movimentacoes = movimentacoes.filter(
            Q(nome__icontains=busca)
            | Q(matricula__icontains=busca)
            | Q(empresa_destino__icontains=busca)
            | Q(equipamento__equipamento__icontains=busca)
            | Q(equipamento__identificador__icontains=busca)
        )
    if status == "em_aberto":
        movimentacoes = movimentacoes.filter(data_devolucao__isnull=True)
    elif status == "atrasado":
        movimentacoes = movimentacoes.filter(
            data_devolucao__isnull=True,
            data_prevista_devolucao__lt=timezone.now(),
        )
    elif status == "devolvido":
        movimentacoes = movimentacoes.filter(data_devolucao__isnull=False)

    return render(
        request,
        "estoque/movimentacao_lista.html",
        {
            "movimentacoes": Paginator(movimentacoes, 25).get_page(
                request.GET.get("page")
            ),
            "busca": busca,
            "status": status,
            "can_manage_movements": is_manager(request.user),
        },
    )


@login_required
def cadastrar_movimentacao(request, equipamento_pk=None):
    if not is_manager(request.user):
        messages.error(
            request, "Somente administradores e gestores podem registrar empréstimos."
        )
        return redirect("estoque:listar_movimentacoes")
    equipamento = (
        get_object_or_404(Equipamento, pk=equipamento_pk)
        if equipamento_pk is not None
        else None
    )
    form = MovimentacaoMaterialForm(
        request.POST or None,
        equipamento=equipamento,
        initial={"data_retirada": timezone.localtime().strftime("%Y-%m-%dT%H:%M")},
    )
    if request.method == "POST" and form.is_valid():
        movimentacao = _salvar_movimentacao(form, request.user)
        if movimentacao:
            log_action(request.user, movimentacao, "create", snapshot(movimentacao))
            messages.success(request, "Retirada registrada com sucesso.")
            return redirect(
                "estoque:detalhe_equipamento", pk=movimentacao.equipamento_id
            )
    return render(
        request,
        "estoque/movimentacao_form.html",
        {"form": form, "equipamento": equipamento, "modo": "cadastrar"},
    )


@login_required
def editar_movimentacao(request, pk):
    if not is_manager(request.user):
        messages.error(
            request, "Somente administradores e gestores podem editar empréstimos."
        )
        return redirect("estoque:listar_movimentacoes")
    movimentacao = get_object_or_404(MovimentacaoMaterial, pk=pk)
    before = snapshot(movimentacao)
    form = MovimentacaoMaterialForm(request.POST or None, instance=movimentacao)
    if request.method == "POST" and form.is_valid():
        movimentacao = _salvar_movimentacao(form, request.user)
        if movimentacao:
            changes = diff(before, snapshot(movimentacao))
            if changes:
                log_action(request.user, movimentacao, "update", changes)
            messages.success(request, "Empréstimo atualizado com sucesso.")
            return redirect("estoque:listar_movimentacoes")
    return render(
        request,
        "estoque/movimentacao_form.html",
        {"form": form, "movimentacao": movimentacao, "modo": "editar"},
    )


@login_required
def devolver_movimentacao(request, pk):
    movimentacao = get_object_or_404(MovimentacaoMaterial, pk=pk)
    if not is_manager(request.user):
        messages.error(
            request, "Somente administradores e gestores podem registrar devoluções."
        )
        return redirect("estoque:listar_movimentacoes")
    if request.method == "POST" and not movimentacao.data_devolucao:
        before = snapshot(movimentacao)
        movimentacao.data_devolucao = timezone.now()
        movimentacao.atualizado_por = request.user
        movimentacao.save(update_fields=["data_devolucao", "atualizado_por", "atualizado_em"])
        log_action(
            request.user,
            movimentacao,
            "update",
            diff(before, snapshot(movimentacao)),
        )
        messages.success(request, "Devolução registrada com sucesso.")
    return redirect("estoque:listar_movimentacoes")


@login_required
def ler_qrcode(request):
    """Página para leitura de QRCode"""
    return render(request, "estoque/qrcode_leitura.html")


@login_required
def estoque_resumido(request):
    search = request.GET.get("search", "")
    equipamentos_base = Equipamento.objects.all()

    agrupados = (
        equipamentos_base.filter(equipamento__icontains=search)
        .values("equipamento")
        .annotate(total_quantidade=Sum("quantidade"), ultimo_registro=Max("registro"))
        .order_by("equipamento")
    )

    equipamentos = []
    hoje = timezone.now().date()

    for item in agrupados:
        registros = equipamentos_base.filter(equipamento=item["equipamento"])
        if not registros.exists():
            continue

        total_certificados = 0
        total_validos = 0
        total_vencidos = 0
        total_sem_certificado = 0
        foto = None
        primeiro_registro = None

        for reg in registros:
            certificacoes = reg.certificacoes.all()
            qtd_certificados = certificacoes.count()
            total_certificados += qtd_certificados
            total_validos += sum(
                1
                for c in certificacoes
                if c.status_vencimento_em(hoje) in {"valido", "vence_em_3_meses"}
            )
            total_vencidos += sum(
                1 for c in certificacoes if c.status_vencimento_em(hoje) == "vencido"
            )
            if qtd_certificados == 0:
                total_sem_certificado += 1
            if not foto and reg.foto:
                foto = reg.foto.url
            if not primeiro_registro:
                primeiro_registro = reg

        equipamentos.append(
            {
                "equipamento": item["equipamento"],
                "total_quantidade": item["total_quantidade"],
                "foto": foto,
                "total_certificado": total_certificados,
                "total_valido": total_validos,
                "total_vencido": total_vencidos,
                "total_sem_certificado": total_sem_certificado,
                "registro": primeiro_registro.registro if primeiro_registro else None,
            }
        )

    # Paginação
    paginator = Paginator(equipamentos, 10)  # 10 por página
    page = request.GET.get("page")
    equipamentos_page = paginator.get_page(page)

    return render(
        request,
        "estoque/estoque_resumido.html",
        {"equipamentos": equipamentos_page, "search": search, "paginator": paginator},
    )


@login_required
def estoque_detalhado(request, nome_equipamento):
    equipamentos = Equipamento.objects.filter(equipamento=nome_equipamento)
    return render(
        request,
        "estoque/estoque_detalhado.html",
        {
            "nome_equipamento": nome_equipamento,
            "equipamentos": equipamentos,
            "today": timezone.now().date(),
        },
    )


@login_required
def listar_certificados(request):
    equipamentos_visiveis = filter_owned_queryset(
        request.user, Equipamento.objects.all()
    )
    certificados_base = Certificacao.objects.filter(
        equipamento__in=equipamentos_visiveis
    ).select_related("equipamento", "criado_por")
    certificados_ativos = certificados_base.filter(ativa=True)

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "salvar_notificacao":
            certificado = get_object_or_404(
                certificados_ativos, pk=request.POST.get("certificado_id")
            )
            ativar = request.POST.get("notificar_por_email") == "on"
            email = request.POST.get("email_notificacao", "").strip()

            if ativar and not certificado.data_vencimento:
                messages.error(
                    request, "Informe uma data de vencimento antes de ativar o aviso."
                )
                return redirect("estoque:listar_certificados")

            if email:
                try:
                    email = normalize_email_recipients(email)
                except ValidationError as exc:
                    messages.error(
                        request,
                        "Revise os destinatários: " + "; ".join(exc.messages),
                    )
                    return redirect("estoque:listar_certificados")
            elif ativar:
                messages.error(request, "Informe ao menos um e-mail destinatário.")
                return redirect("estoque:listar_certificados")

            before = snapshot(certificado)
            email_alterado = certificado.email_notificacao != email
            certificado.notificar_por_email = ativar
            certificado.email_notificacao = email
            if ativar and email_alterado:
                certificado.notificacao_enviada_em = None
                certificado.vencimento_notificado = None
            certificado.save(
                update_fields=[
                    "notificar_por_email",
                    "email_notificacao",
                    "notificacao_enviada_em",
                    "vencimento_notificado",
                ]
            )
            changes = diff(before, snapshot(certificado))
            if changes:
                log_action(request.user, certificado, "update", changes)
            messages.success(request, "Preferências de notificação atualizadas.")
            return redirect("estoque:listar_certificados")

        if acao == "enviar_notificacoes":
            if not is_manager(request.user):
                messages.error(
                    request, "Somente gestores podem executar a verificação de avisos."
                )
                return redirect("estoque:listar_certificados")

            resultado = enviar_avisos_certificados(certificados_ativos)
            if resultado["erros"]:
                detalhe = resultado["erros"][0]["erro"]
                messages.warning(
                    request,
                    f"{resultado['enviados']} aviso(s) enviado(s) e "
                    f"{len(resultado['erros'])} envio(s) com erro. {detalhe}",
                )
            else:
                messages.success(
                    request, f"{resultado['enviados']} aviso(s) enviado(s)."
                )
            return redirect("estoque:listar_certificados")

    hoje = timezone.localdate()
    limite_alerta = Certificacao.adicionar_meses(hoje, 3)
    resumo = {
        "total": certificados_ativos.count(),
        "vencidos": certificados_ativos.filter(data_vencimento__lt=hoje).count(),
        "proximos": certificados_ativos.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=limite_alerta,
        ).count(),
        "validos": certificados_ativos.filter(
            data_vencimento__gt=limite_alerta
        ).count(),
        "avisos_pendentes": certificados_para_notificar(
            certificados_ativos, hoje
        ).count(),
    }

    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    exibir_historico = request.GET.get("historico") == "1" or status == "substituido"
    certificados = certificados_base if exibir_historico else certificados_ativos

    if busca:
        certificados = certificados.filter(
            Q(nome_certificado__icontains=busca)
            | Q(codigo_certificado__icontains=busca)
            | Q(empresa_certificadora__icontains=busca)
            | Q(equipamento__equipamento__icontains=busca)
            | Q(equipamento__identificador__icontains=busca)
        )

    if status == "vencido":
        certificados = certificados.filter(data_vencimento__lt=hoje)
    elif status == "vence_em_3_meses":
        certificados = certificados.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=limite_alerta,
        )
    elif status == "valido":
        certificados = certificados.filter(data_vencimento__gt=limite_alerta)
    elif status == "sem_vencimento":
        certificados = certificados.filter(data_vencimento__isnull=True)
    elif status == "substituido":
        certificados = certificados.filter(ativa=False)

    certificados = certificados.order_by(
        "-ativa", "data_vencimento", "equipamento__equipamento"
    )
    pagina = Paginator(certificados, 20).get_page(request.GET.get("page"))

    return render(
        request,
        "estoque/certificacao_lista.html",
        {
            "certificados": pagina,
            "busca": busca,
            "status": status,
            "resumo": resumo,
            "exibir_historico": exibir_historico,
            "email_status": email_delivery_status(),
        },
    )


@login_required
def editar_certificacao(request, pk):
    equipamentos_visiveis = filter_owned_queryset(
        request.user, Equipamento.objects.all()
    )
    certificado = get_object_or_404(
        Certificacao.objects.select_related("equipamento").filter(
            equipamento__in=equipamentos_visiveis
        ),
        pk=pk,
        ativa=True,
    )
    if not can_edit_object(request.user, certificado):
        messages.error(request, "Você não tem permissão para editar este certificado.")
        return redirect("estoque:listar_certificados")

    before = snapshot(certificado)
    vencimento_anterior = certificado.data_vencimento
    form = CertificacaoEdicaoForm(
        request.POST or None, request.FILES or None, instance=certificado
    )
    if request.method == "POST" and form.is_valid():
        certificado = form.save(commit=False)
        certificado.atualizado_por = request.user
        if vencimento_anterior != certificado.data_vencimento:
            certificado.notificacao_enviada_em = None
            certificado.vencimento_notificado = None
        certificado.save()
        changes = diff(before, snapshot(certificado))
        if changes:
            log_action(request.user, certificado, "update", changes)
        messages.success(request, "Certificado atualizado com sucesso.")
        return redirect("estoque:listar_certificados")

    return render(
        request,
        "estoque/certificacao_form.html",
        {
            "form": form,
            "certificado": certificado,
            "modo": "editar",
        },
    )


@login_required
def renovar_certificacao(request, pk):
    equipamentos_visiveis = filter_owned_queryset(
        request.user, Equipamento.objects.all()
    )
    certificado = get_object_or_404(
        Certificacao.objects.select_related("equipamento").filter(
            equipamento__in=equipamentos_visiveis,
            ativa=True,
        ),
        pk=pk,
    )
    if not can_edit_object(request.user, certificado):
        messages.error(request, "Você não tem permissão para renovar este certificado.")
        return redirect("estoque:listar_certificados")

    initial = {
        "nome_certificado": certificado.nome_certificado,
        "empresa_certificadora": certificado.empresa_certificadora,
        "detalhes": certificado.detalhes,
        "notificar_por_email": certificado.notificar_por_email,
        "email_notificacao": certificado.email_notificacao,
    }
    form = CertificacaoRenovacaoForm(
        request.POST or None, request.FILES or None, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            nova_certificacao = form.save(commit=False)
            nova_certificacao.equipamento = certificado.equipamento
            nova_certificacao.certificacao_anterior = certificado
            nova_certificacao.criado_por = request.user
            nova_certificacao.atualizado_por = request.user
            nova_certificacao.ativa = True
            nova_certificacao.save()

            before = snapshot(certificado)
            certificado.ativa = False
            certificado.atualizado_por = request.user
            certificado.notificar_por_email = False
            certificado.save(
                update_fields=["ativa", "atualizado_por", "notificar_por_email"]
            )
            log_action(
                request.user, certificado, "update", diff(before, snapshot(certificado))
            )
            log_action(
                request.user, nova_certificacao, "create", snapshot(nova_certificacao)
            )

        messages.success(
            request,
            "Certificado renovado. O documento anterior foi preservado no histórico.",
        )
        return redirect("estoque:listar_certificados")

    return render(
        request,
        "estoque/certificacao_form.html",
        {
            "form": form,
            "certificado": certificado,
            "modo": "renovar",
        },
    )


@login_required
def autocomplete_equipamento(request):
    """Endpoint AJAX para autocompletar nomes de equipamentos"""
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        return JsonResponse({"erro": "Requisição AJAX obrigatória."}, status=400)

    term = request.GET.get("term", "").upper()
    equipamentos = (
        filter_owned_queryset(
            request.user,
            Equipamento.objects.filter(equipamento__icontains=term),
        )
        .values_list("equipamento", flat=True)
        .distinct()
    )
    return JsonResponse(list(equipamentos), safe=False)
