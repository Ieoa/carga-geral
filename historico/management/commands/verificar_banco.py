from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Verifica conexao, servidor, tabelas essenciais e migrations pendentes."

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
            tables = set(connection.introspection.table_names())
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            pending = executor.migration_plan(targets)
        except Exception as exc:
            raise CommandError(f"Falha ao conectar ou inspecionar o banco: {exc}") from exc

        engine = connection.settings_dict["ENGINE"]
        vendor = connection.vendor
        version = getattr(connection, "mysql_version", None)
        host = connection.settings_dict.get("HOST") or "localhost"
        port = connection.settings_dict.get("PORT") or "3306"
        self.stdout.write(f"Engine: {engine}")
        self.stdout.write(f"Vendor: {vendor}")
        self.stdout.write(f"Servidor: {host}:{port}")
        if version:
            self.stdout.write(f"Versao: {version}")
        self.stdout.write(f"Tabelas encontradas: {len(tables)}")

        if engine != "django.db.backends.mysql" or vendor != "mysql":
            raise CommandError("O LOGGERAL deve usar obrigatoriamente um servidor MySQL.")

        required_tables = {
            "django_migrations",
            "auth_user",
            "historico_navio",
            "historico_useraccess",
            "estoque_equipamento",
        }
        missing = sorted(required_tables - tables)
        if missing:
            raise CommandError("Tabelas obrigatorias ausentes: " + ", ".join(missing))
        if pending:
            names = [migration.name for migration, backwards in pending if not backwards]
            raise CommandError("Migrations pendentes: " + ", ".join(names))

        self.stdout.write(self.style.SUCCESS("Banco conectado, migrado e com tabelas essenciais."))
