from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from estoque.models import Certificacao

from .email_recipients import parse_email_recipients

NON_DELIVERY_BACKENDS = {
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.dummy.EmailBackend',
}


def email_delivery_status():
    if settings.EMAIL_BACKEND in NON_DELIVERY_BACKENDS:
        return {
            'enabled': False,
            'message': 'O SMTP não está configurado. O modo atual apenas simula o envio.',
        }
    if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend') and not settings.EMAIL_HOST:
        return {
            'enabled': False,
            'message': 'O servidor SMTP não foi informado na configuração.',
        }
    return {'enabled': True, 'message': 'Servidor de e-mail configurado.'}


def certificados_para_notificar(queryset=None, referencia=None):
    referencia = referencia or timezone.localdate()
    limite = Certificacao.adicionar_meses(referencia, 3)
    queryset = queryset if queryset is not None else Certificacao.objects.all()

    return (
        queryset.filter(
            ativa=True,
            notificar_por_email=True,
            data_vencimento__gte=referencia,
            data_vencimento__lte=limite,
        )
        .exclude(email_notificacao='')
        .filter(
            Q(vencimento_notificado__isnull=True)
            | ~Q(vencimento_notificado=F('data_vencimento'))
        )
        .select_related('equipamento')
        .order_by('data_vencimento', 'equipamento__equipamento')
    )


def enviar_avisos_certificados(queryset=None, referencia=None):
    referencia = referencia or timezone.localdate()
    enviados = 0
    erros = []

    delivery_status = email_delivery_status()
    if not delivery_status['enabled']:
        return {
            'enviados': 0,
            'erros': [{
                'certificado': None,
                'erro': delivery_status['message'],
            }],
        }

    candidate_ids = list(
        certificados_para_notificar(queryset, referencia).values_list('pk', flat=True)
    )
    for certificate_id in candidate_ids:
        with transaction.atomic():
            locked_queryset = Certificacao.objects.select_for_update().filter(pk=certificate_id)
            certificado = certificados_para_notificar(locked_queryset, referencia).first()
            if certificado is None:
                continue

            equipamento = certificado.equipamento
            assunto = f'Certificado próximo do vencimento: {certificado.nome_certificado}'
            mensagem = (
                'Olá,\n\n'
                f'O certificado "{certificado.nome_certificado}" do material '
                f'"{equipamento.equipamento}" ({equipamento.identificador}) vence em '
                f'{certificado.data_vencimento:%d/%m/%Y}.\n\n'
                f'Código do certificado: {certificado.codigo_certificado or "Não informado"}\n'
                f'Empresa certificadora: {certificado.empresa_certificadora}\n\n'
                'Acesse o sistema Carga Geral para consultar o documento e providenciar a renovação.'
            )

            try:
                recipients = parse_email_recipients(certificado.email_notificacao)
                if not recipients:
                    raise RuntimeError('Nenhum destinatário válido foi informado.')
                delivered = send_mail(
                    assunto,
                    mensagem,
                    settings.DEFAULT_FROM_EMAIL,
                    recipients,
                    fail_silently=False,
                )
                if delivered != 1:
                    raise RuntimeError('O servidor de e-mail não confirmou a entrega da mensagem.')
            # Backends podem lançar erros de rede, autenticação, TLS e protocolo.
            except Exception as exc:  # noqa: BLE001
                erros.append({'certificado': certificado.pk, 'erro': str(exc)})
                continue

            certificado.notificacao_enviada_em = timezone.now()
            certificado.vencimento_notificado = certificado.data_vencimento
            certificado.save(update_fields=['notificacao_enviada_em', 'vencimento_notificado'])
            enviados += 1

    return {'enviados': enviados, 'erros': erros}
