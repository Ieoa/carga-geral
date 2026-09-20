from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from historico.models import UserAccess
from historico.security import create_user_with_temporary_password


class Command(BaseCommand):
    help = "Aplica migrations e cria o administrador inicial da instalacao MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin_inicial")
        parser.add_argument("--skip-migrate", action="store_true")
        parser.add_argument("--promote-existing", action="store_true")

    def handle(self, *args, **options):
        if not options["skip_migrate"]:
            call_command("migrate", interactive=False, verbosity=1)

        username = options["username"]
        user = User.objects.filter(username=username).first()
        if user:
            if not (user.is_staff and user.is_superuser):
                if not options["promote_existing"]:
                    raise CommandError(
                        f"O usuário '{username}' já existe sem privilégios administrativos. "
                        "Use outro --username ou confirme conscientemente com --promote-existing."
                    )
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
            UserAccess.objects.get_or_create(user=user)
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
