import json
from datetime import date

from django.core.exceptions import ValidationError

from historico.uploads import validate_pdf_upload

from .email_recipients import normalize_email_recipients


def parse_certificate_payloads(request):
    raw_payload = request.POST.get("certificados_json", "[]")
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("Os dados dos certificados estão inválidos.") from exc
    if not isinstance(payload, list):
        raise ValidationError("A lista de certificados está inválida.")
    if len(payload) > 30:
        raise ValidationError("Cadastre no máximo 30 certificados por equipamento.")

    normalized = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValidationError(f"O certificado {index + 1} está inválido.")
        name = str(item.get("nome") or "").strip()
        company = str(item.get("empresa") or "").strip()
        code = str(item.get("codigo") or "").strip()
        if not name or not company or not code:
            raise ValidationError(f"Informe nome, empresa e código no certificado {index + 1}.")

        issued_at = _parse_date(item.get("data"), f"emissão do certificado {index + 1}", required=True)
        expires_at = _parse_date(item.get("vencimento"), f"vencimento do certificado {index + 1}")
        if expires_at and expires_at < issued_at:
            raise ValidationError(f"O vencimento do certificado {index + 1} não pode ser anterior à emissão.")

        notify = item.get("notificar") is True
        email = str(item.get("email") or "").strip()
        if notify:
            if not expires_at:
                raise ValidationError(f"Informe o vencimento para notificar o certificado {index + 1}.")
            try:
                email = normalize_email_recipients(email)
            except ValidationError as exc:
                raise ValidationError(
                    f"Os e-mails do certificado {index + 1} são inválidos: "
                    + "; ".join(exc.messages)
                ) from exc

        attachment = request.FILES.get(f"anexo_{index}")
        if attachment:
            validate_pdf_upload(attachment, limit=10 * 1024 * 1024)
        normalized.append({
            "nome_certificado": name,
            "empresa_certificadora": company,
            "data_certificacao": issued_at,
            "data_vencimento": expires_at,
            "codigo_certificado": code,
            "detalhes": str(item.get("detalhes") or "").strip(),
            "anexo": attachment,
            "notificar_por_email": notify,
            "email_notificacao": email if notify else "",
        })
    return normalized


def _parse_date(value, label, *, required=False):
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise ValidationError(f"Informe a data de {label}.")
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError(f"A data de {label} é inválida.") from exc
