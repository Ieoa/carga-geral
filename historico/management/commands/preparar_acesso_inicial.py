from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from historico.security import create_user_with_temporary_password


class Command(BaseCommand):
    help = "Aplica migrations e cria o administrador inicial da instalacao MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin_inicial")
        parser.add_argument("--skip-migrate", action="store_true")

    def handle(self, *args, **options):
        if not options["skip_migrate"]:
            call_command("migrate", interactive=False, verbosity=1)

        username = options["username"]
        user = User.objects.filter(username=username).first()
        if user:
            changed = []
            if not user.is_staff:
                user.is_staff = True
                changed.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                changed.append("is_superuser")
            if changed:
                user.save(update_fields=changed)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador inicial '{username}' ja existe; senha preservada."
                )
            )
            self.stdout.write(
                f"Para gerar outra senha: python manage.py provisionar_acesso {username}"
            )
            return

        user, temporary_password = create_user_with_temporary_password(
            username=username,
            email="admin.inicial@localhost",
            first_name="Administrador",
            last_name="Local",
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])

        self.stdout.write(self.style.SUCCESS("Primeiro acesso criado no MySQL."))
        self.stdout.write(f"Usuario: {username}")
        self.stdout.write(f"Senha temporaria: {temporary_password}")
        self.stdout.write("A senha deve ser alterada no primeiro login.")
