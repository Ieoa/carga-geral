from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from historico.security import issue_temporary_password


class Command(BaseCommand):
    help = 'Gera uma senha temporária aleatória e exige troca no próximo acesso.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError('Usuário não encontrado.') from exc

        temporary_password = issue_temporary_password(user)
        self.stdout.write(self.style.SUCCESS(f'Usuário: {user.username}'))
        self.stdout.write(self.style.WARNING(f'Senha temporária: {temporary_password}'))
        self.stdout.write('A senha deverá ser alterada no próximo acesso.')
