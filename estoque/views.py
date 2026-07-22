"""
Views para sistema de estoque com autenticação e CRUD para colaboradores e equipamentos.
Organizado seguindo boas práticas Pythonicas com imports agrupados e comentários descritivos.
"""

# Standard Library
import json
import re

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q, Sum, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.paginator import Paginator

# Local Apps
from .forms import ColaboradorForm, EquipamentoForm
from .models import Certificacao, Colaborador, Equipamento
from historico.audit import diff, log_action, snapshot
from historico.permissions import can_manage_users, filter_owned_queryset, is_manager
from .services.certificacoes import certificados_para_notificar, enviar_avisos_certificados


class CustomLoginView(LoginView):
    """View personalizada para login que redireciona usuários autenticados"""
    
    template_name = 'estoque/home.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Redireciona usuários já autenticados para o dashboard"""
        if request.user.is_authenticated:
            return redirect('estoque:dashboard')
        return super().dispatch(request, *args, **kwargs)


@login_required
def dashboard(request):
    """Página inicial após login"""
    return render(request, 'estoque/dashboard.html')


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
        messages.error(request, 'Somente administradores podem cadastrar usuários.')
        return redirect('estoque:dashboard')

    if request.method == 'POST':
        form = ColaboradorForm(request.POST)
        if form.is_valid():
            try:
                colaborador = form.save(commit=False)
                nomes = colaborador.nome.strip().split()
                
                # Gera senha a partir dos 6 primeiros dígitos do CPF
                cpf_numeros = re.sub(r'[^0-9]', '', colaborador.cpf)
                senha = cpf_numeros[:6]
                
                # Cria usuário Django associado
                user = User.objects.create_user(
                    username=colaborador.matricula,
                    email=colaborador.email,
                    first_name=nomes[0],
                    last_name=' '.join(nomes[1:]) if len(nomes) > 1 else '',
                    password=senha
                )
                
                # Completa e salva o colaborador
                colaborador.user = user
                colaborador.data_criacao = timezone.now()
                colaborador.save()
                log_action(request.user, colaborador, "create", snapshot(colaborador))
                
                messages.success(request, 'Colaborador cadastrado com sucesso!')
                return redirect('estoque:cadastrar_colaborador')
                
            except Exception as e:
                messages.error(request, f'Erro ao cadastrar colaborador: {str(e)}')
    else:
        form = ColaboradorForm()

    return render(request, 'estoque/cadastro_colaborador.html', {
        'colaborador_form': form
    })


@login_required
def listar_colaboradores(request):
    """Lista todos os colaboradores cadastrados"""
    if not can_manage_users(request.user):
        messages.error(request, 'Somente administradores podem acessar colaboradores.')
        return redirect('estoque:dashboard')
    colaboradores = Colaborador.objects.all()
    return render(request, 'estoque/colaboradores.html', {
        'colaboradores': colaboradores
    })


@login_required
def editar_colaborador(request, pk):
    """Edita informações de um colaborador existente"""
    if not can_manage_users(request.user):
        messages.error(request, 'Somente administradores podem editar colaboradores.')
        return redirect('estoque:dashboard')
    colaborador = get_object_or_404(Colaborador, pk=pk)

    if request.method == 'POST':
        before = snapshot(colaborador)
        form = ColaboradorForm(request.POST, instance=colaborador)
        if form.is_valid():
            colaborador = form.save()
            # Atualiza dados do usuário associado
            colaborador.user.email = colaborador.email
            colaborador.user.first_name = colaborador.nome.split()[0]
            colaborador.user.last_name = ' '.join(colaborador.nome.split()[1:])
            colaborador.user.save()
            changes = diff(before, snapshot(colaborador))
            if changes:
                log_action(request.user, colaborador, "update", changes)
            
            messages.success(request, 'Colaborador atualizado com sucesso!')
            return redirect('estoque:listar_colaboradores')
    else:
        form = ColaboradorForm(instance=colaborador)

    return render(request, 'estoque/editar_colaborador.html', {
        'form': form,
        'colaborador': colaborador
    })


@login_required
def excluir_colaborador(request, pk):
    """Remove colaborador e usuário associado"""
    if not can_manage_users(request.user):
        messages.error(request, 'Somente administradores podem excluir colaboradores.')
        return redirect('estoque:dashboard')
    colaborador = get_object_or_404(Colaborador, pk=pk)

    if request.method == 'POST':
        before = snapshot(colaborador)
        log_action(request.user, colaborador, "delete", before)
        if colaborador.user:
            colaborador.user.delete()  # Remove usuário vinculado
        colaborador.delete()
        messages.success(request, 'Colaborador excluído com sucesso!')
        return redirect('estoque:listar_colaboradores')

    return render(request, 'estoque/excluir_colaborador.html', {
        'colaborador': colaborador
    })


# ==============================================
# VIEWS PARA GESTÃO DE EQUIPAMENTOS
# ==============================================

@login_required
def cadastrar_equipamento(request):
    """Cadastra novo equipamento com certificados associados"""
    if request.method == 'POST':
        form = EquipamentoForm(request.POST, request.FILES)
        
        if form.is_valid():
            equipamento = form.save(commit=False)
            equipamento.criado_por = request.user
            equipamento.atualizado_por = request.user
            equipamento.save()
            log_action(request.user, equipamento, "create", snapshot(equipamento))
            certificados_data = json.loads(request.POST.get('certificados_json', '[]'))
            
            # Processa cada certificado enviado
            for idx, cert_data in enumerate(certificados_data):
                anexo_file = request.FILES.get(f'anexo_{idx}')
                
                certificacao = Certificacao.objects.create(
                    equipamento=equipamento,
                    nome_certificado=cert_data.get('nome'),
                    empresa_certificadora=cert_data.get('empresa'),
                    data_certificacao=cert_data.get('data') or None,
                    data_vencimento=cert_data.get('vencimento') or None,
                    codigo_certificado=cert_data.get('codigo'),
                    detalhes=cert_data.get('detalhes'),
                    anexo=anexo_file,
                    notificar_por_email=bool(cert_data.get('notificar')),
                    email_notificacao=cert_data.get('email', '').strip(),
                    criado_por=request.user,
                )
                log_action(request.user, certificacao, "create", snapshot(certificacao))

            messages.success(request, 'Equipamento cadastrado com sucesso!')
            return render(request, 'estoque/equipamento_cadastro.html', {
                'form': EquipamentoForm(),
                'qr_code': equipamento.qrcode.url,
                'exibir_modal': True
            })
        else:
            return render(request, 'estoque/equipamento_cadastro.html', {'form': form})
    else:
        form = EquipamentoForm()

    return render(request, 'estoque/equipamento_cadastro.html', {'form': form})


@login_required
def listar_equipamentos(request):
    """Lista equipamentos com possibilidade de busca"""
    busca = request.GET.get('q', '')
    equipamentos = filter_owned_queryset(request.user, Equipamento.objects.all())

    if busca:
        equipamentos = equipamentos.filter(
            Q(equipamento__icontains=busca) |
            Q(identificador__icontains=busca) |
            Q(registro__icontains=busca)
        )

    return render(request, 'estoque/equipamento_lista.html', {
        'equipamentos': equipamentos,
        'busca': busca
    })
    

@login_required
def detalhe_equipamento(request, pk):
    
    equipamento = get_object_or_404(filter_owned_queryset(request.user, Equipamento.objects.all()), pk=pk)
    today = timezone.now().date()
    return render(request, 'estoque/equipamento_detalhe.html', {
        'equipamento': equipamento,
        'today': today
    })


@login_required
def ler_qrcode(request):
    """Página para leitura de QRCode"""
    return render(request, 'estoque/qrcode_leitura.html')



@login_required
def estoque_resumido(request):
    search = request.GET.get('search', '')
    equipamentos_base = filter_owned_queryset(request.user, Equipamento.objects.all())

    agrupados = (
        equipamentos_base
        .filter(equipamento__icontains=search)
        .values('equipamento')
        .annotate(
            total_quantidade=Sum('quantidade'),
            ultimo_registro=Max('registro')
        )
        .order_by('equipamento')
    )

    equipamentos = []
    hoje = timezone.now().date()

    for item in agrupados:
        registros = equipamentos_base.filter(equipamento=item['equipamento'])
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
                if c.status_vencimento_em(hoje) in {'valido', 'vence_em_3_meses'}
            )
            total_vencidos += sum(1 for c in certificacoes if c.status_vencimento_em(hoje) == 'vencido')
            if qtd_certificados == 0:
                total_sem_certificado += 1
            if not foto and reg.foto:
                foto = reg.foto.url
            if not primeiro_registro:
                primeiro_registro = reg

        equipamentos.append({
            'equipamento': item['equipamento'],
            'total_quantidade': item['total_quantidade'],
            'foto': foto,
            'total_certificado': total_certificados,
            'total_valido': total_validos,
            'total_vencido': total_vencidos,
            'total_sem_certificado': total_sem_certificado,
            'registro': primeiro_registro.registro if primeiro_registro else None
        })

    # Paginação
    paginator = Paginator(equipamentos, 10)  # 10 por página
    page = request.GET.get('page')
    equipamentos_page = paginator.get_page(page)

    return render(request, 'estoque/estoque_resumido.html', {
        'equipamentos': equipamentos_page,
        'search': search,
        'paginator': paginator
    })


@login_required
def estoque_detalhado(request, nome_equipamento):
    equipamentos = filter_owned_queryset(
        request.user,
        Equipamento.objects.filter(equipamento=nome_equipamento),
    )
    return render(request, 'estoque/estoque_detalhado.html', {
        'nome_equipamento': nome_equipamento,
        'equipamentos': equipamentos,
        'today': timezone.now().date()
    })


@login_required
def listar_certificados(request):
    equipamentos_visiveis = filter_owned_queryset(request.user, Equipamento.objects.all())
    certificados_base = Certificacao.objects.filter(
        equipamento__in=equipamentos_visiveis
    ).select_related('equipamento', 'criado_por')

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'salvar_notificacao':
            certificado = get_object_or_404(certificados_base, pk=request.POST.get('certificado_id'))
            ativar = request.POST.get('notificar_por_email') == 'on'
            email = request.POST.get('email_notificacao', '').strip()

            if ativar and not certificado.data_vencimento:
                messages.error(request, 'Informe uma data de vencimento antes de ativar o aviso.')
                return redirect('estoque:listar_certificados')

            if ativar:
                try:
                    validate_email(email)
                except ValidationError:
                    messages.error(request, 'Informe um endereço de e-mail válido para ativar o aviso.')
                    return redirect('estoque:listar_certificados')

            before = snapshot(certificado)
            email_alterado = certificado.email_notificacao != email
            certificado.notificar_por_email = ativar
            certificado.email_notificacao = email
            if ativar and email_alterado:
                certificado.notificacao_enviada_em = None
                certificado.vencimento_notificado = None
            certificado.save(update_fields=[
                'notificar_por_email',
                'email_notificacao',
                'notificacao_enviada_em',
                'vencimento_notificado',
            ])
            changes = diff(before, snapshot(certificado))
            if changes:
                log_action(request.user, certificado, 'update', changes)
            messages.success(request, 'Preferências de notificação atualizadas.')
            return redirect('estoque:listar_certificados')

        if acao == 'enviar_notificacoes':
            if not is_manager(request.user):
                messages.error(request, 'Somente gestores podem executar a verificação de avisos.')
                return redirect('estoque:listar_certificados')

            resultado = enviar_avisos_certificados(certificados_base)
            if resultado['erros']:
                messages.warning(
                    request,
                    f"{resultado['enviados']} aviso(s) enviado(s) e "
                    f"{len(resultado['erros'])} envio(s) com erro.",
                )
            else:
                messages.success(request, f"{resultado['enviados']} aviso(s) enviado(s).")
            return redirect('estoque:listar_certificados')

    hoje = timezone.localdate()
    limite_alerta = Certificacao.adicionar_meses(hoje, 3)
    resumo = {
        'total': certificados_base.count(),
        'vencidos': certificados_base.filter(data_vencimento__lt=hoje).count(),
        'proximos': certificados_base.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=limite_alerta,
        ).count(),
        'validos': certificados_base.filter(data_vencimento__gt=limite_alerta).count(),
        'avisos_pendentes': certificados_para_notificar(certificados_base, hoje).count(),
    }

    busca = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    certificados = certificados_base

    if busca:
        certificados = certificados.filter(
            Q(nome_certificado__icontains=busca)
            | Q(codigo_certificado__icontains=busca)
            | Q(empresa_certificadora__icontains=busca)
            | Q(equipamento__equipamento__icontains=busca)
            | Q(equipamento__identificador__icontains=busca)
        )

    if status == 'vencido':
        certificados = certificados.filter(data_vencimento__lt=hoje)
    elif status == 'vence_em_3_meses':
        certificados = certificados.filter(
            data_vencimento__gte=hoje,
            data_vencimento__lte=limite_alerta,
        )
    elif status == 'valido':
        certificados = certificados.filter(data_vencimento__gt=limite_alerta)
    elif status == 'sem_vencimento':
        certificados = certificados.filter(data_vencimento__isnull=True)

    certificados = certificados.order_by('data_vencimento', 'equipamento__equipamento')
    pagina = Paginator(certificados, 20).get_page(request.GET.get('page'))

    return render(request, 'estoque/certificacao_lista.html', {
        'certificados': pagina,
        'busca': busca,
        'status': status,
        'resumo': resumo,
    })
    

@login_required
def autocomplete_equipamento(request):
    """Endpoint AJAX para autocompletar nomes de equipamentos"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        term = request.GET.get('term', '').upper()
        equipamentos = filter_owned_queryset(
            request.user,
            Equipamento.objects.filter(equipamento__icontains=term),
        ).values_list('equipamento', flat=True).distinct()
        return JsonResponse(list(equipamentos), safe=False)
