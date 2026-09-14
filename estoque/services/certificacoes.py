from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F, Q
from django.utils import timezone

from estoque.models import Certificacao


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

    for certificado in certificados_para_notificar(queryset, referencia):
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
            send_mail(
                assunto,
                mensagem,
                settings.DEFAULT_FROM_EMAIL,
                [certificado.email_notificacao],
                fail_silently=False,
            )
        except Exception as exc:
            erros.append({'certificado': certificado.pk, 'erro': str(exc)})
            continue

        certificado.notificacao_enviada_em = timezone.now()
        certificado.vencimento_notificado = certificado.data_vencimento
        certificado.save(update_fields=['notificacao_enviada_em', 'vencimento_notificado'])
        enviados += 1

    return {'enviados': enviados, 'erros': erros}
