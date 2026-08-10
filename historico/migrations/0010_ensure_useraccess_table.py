from django.db import migrations


def ensure_useraccess_table(apps, schema_editor):
    """Repara bancos onde 0008 foi marcada como aplicada sem criar a tabela."""
    UserAccess = apps.get_model("historico", "UserAccess")
    table_name = UserAccess._meta.db_table
    existing_tables = set(schema_editor.connection.introspection.table_names())
    if table_name not in existing_tables:
        schema_editor.create_model(UserAccess)


class Migration(migrations.Migration):
    dependencies = [
        ("historico", "0009_invalidate_predictable_passwords"),
    ]

    operations = [
        migrations.RunPython(ensure_useraccess_table, migrations.RunPython.noop),
    ]
