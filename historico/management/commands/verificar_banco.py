from django.apps import apps
from django.conf import settings
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
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONVERT_TZ('2026-01-01 12:00:00', 'UTC', 'America/Sao_Paulo')")
                timezone_conversion = cursor.fetchone()[0]
                cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                ssl_row = cursor.fetchone()
                ssl_cipher = ssl_row[1] if ssl_row else ""
                cursor.execute("SELECT @@character_set_connection, @@collation_connection, @@sql_mode")
                charset, collation, sql_mode = cursor.fetchone()
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
            model._meta.db_table
            for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
        }
        missing = sorted(required_tables - tables)
        if missing:
            raise CommandError("Tabelas obrigatorias ausentes: " + ", ".join(missing))
        if pending:
            names = [migration.name for migration, backwards in pending if not backwards]
            raise CommandError("Migrations pendentes: " + ", ".join(names))

        if timezone_conversion is None:
            self.stdout.write(self.style.WARNING(
                "Tabelas de fuso horario do MySQL nao carregadas. O LOGGERAL usa intervalos UTC e continua funcional."
            ))
        self.stdout.write(f"Charset/collation: {charset}/{collation}")
        self.stdout.write(f"SQL mode: {sql_mode}")
        if ssl_cipher:
            self.stdout.write(f"TLS MySQL: ativo ({ssl_cipher})")
        elif settings.DATABASES["default"].get("OPTIONS", {}).get("ssl"):
            raise CommandError("TLS foi configurado para o MySQL, mas a sessao nao esta criptografada.")
        else:
            self.stdout.write(self.style.WARNING("TLS MySQL: nao detectado; valide a politica da TI para a intranet."))

        self.stdout.write(self.style.SUCCESS("Banco conectado, migrado e com tabelas essenciais."))
