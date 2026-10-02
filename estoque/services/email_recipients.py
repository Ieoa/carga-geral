import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

MAX_NOTIFICATION_RECIPIENTS = 20


def parse_email_recipients(value):
    """Valida uma lista separada por vírgula, ponto e vírgula ou quebra de linha."""
    raw_items = [item.strip() for item in re.split(r"[;,\s]+", value or "") if item.strip()]
    if len(raw_items) > MAX_NOTIFICATION_RECIPIENTS:
        raise ValidationError(
            f"Informe no máximo {MAX_NOTIFICATION_RECIPIENTS} destinatários."
        )

    recipients = []
    seen = set()
    invalid = []
    for item in raw_items:
        try:
            validate_email(item)
        except ValidationError:
            invalid.append(item)
            continue
        normalized_key = item.casefold()
        if normalized_key not in seen:
            recipients.append(item)
            seen.add(normalized_key)

    if invalid:
        raise ValidationError(
            "E-mail(s) inválido(s): " + ", ".join(invalid)
        )
    return recipients


def normalize_email_recipients(value):
    return "; ".join(parse_email_recipients(value))
