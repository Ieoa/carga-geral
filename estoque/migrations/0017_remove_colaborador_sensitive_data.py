from django.db import migrations


SENSITIVE_KEYS = {"cpf", "email"}


def _scrub(value):
    if isinstance(value, dict):
        return {
            key: _scrub(item)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def purge_stock_sensitive_data(apps, schema_editor):
    Colaborador = apps.get_model("estoque", "Colaborador")
    AuditLog = apps.get_model("historico", "AuditLog")
    User = apps.get_model("auth", "User")

    user_ids = Colaborador.objects.exclude(user_id=None).values_list(
        "user_id", flat=True
    )
    User.objects.filter(pk__in=user_ids).update(email="")

    for log in AuditLog.objects.filter(model_name__iexact="colaborador").iterator():
        cleaned = _scrub(log.changes)
        if cleaned != log.changes:
            log.changes = cleaned
            log.save(update_fields=["changes"])


class Migration(migrations.Migration):
    dependencies = [
        ("historico", "0011_remove_colaborador_sensitive_data"),
        ("estoque", "0016_certificacao_ativa_certificacao_atualizado_por_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="colaborador", name="cpf"),
        migrations.RemoveField(model_name="colaborador", name="email"),
        migrations.RunPython(purge_stock_sensitive_data, migrations.RunPython.noop),
    ]
