from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from estoque.models import Colaborador
from historico.security import issue_temporary_password

DEMO_ACCOUNTS = (
    {
        'username': 'admin_demo',
        'nome': 'Administrador Demo',
        'email': 'admin.demo@exemplo.local',
        'profile': 'Administrador',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'gestor_demo',
        'nome': 'Gestor Demo',
        'email': 'gestor.demo@exemplo.local',
        'cpf': '900.000.000-01',
        'cargo': 'GER',
        'profile': 'Gestor',
    },
    {
        'username': 'comum_demo',
        'nome': 'Colaborador Demo',
        'email': 'comum.demo@exemplo.local',
        'cpf': '900.000.000-02',
        'cargo': 'AUX',
        'profile': 'Colaborador',
    },
)


class Command(BaseCommand):
    help = 'Cria contas locais de demonstracao com senhas temporarias aleatorias.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Este comando so pode ser executado com DEBUG=True.')

        expected_table = 'historico_useraccess'
        if expected_table not in connection.introspection.table_names():
            raise CommandError(
                f"A tabela {expected_table} ainda nao existe. "
                "Execute 'python manage.py migrate' antes de criar os usuarios demo."
            )

        credentials = []
        with transaction.atomic():
            for account in DEMO_ACCOUNTS:
                user, _ = User.objects.get_or_create(username=account['username'])
                names = account['nome'].split(maxsplit=1)
                user.first_name = names[0]
                user.last_name = names[1] if len(names) > 1 else ''
                user.email = account['email']
                user.is_active = True
                user.is_staff = account.get('is_staff', False)
                user.is_superuser = account.get('is_superuser', False)
                user.save()

                if 'cargo' in account:
                    Colaborador.objects.update_or_create(
                        user=user,
                        defaults={
                            'matricula': account['username'],
                            'nome': account['nome'],
                            'email': account['email'],
                            'cpf': account['cpf'],
                            'area': 'OP',
                            'cargo': account['cargo'],
                        },
                    )

                password = issue_temporary_password(user)
                credentials.append((account['username'], password, account['profile']))

        self.stdout.write(self.style.SUCCESS('Contas de demonstracao preparadas:'))
        for username, password, profile in credentials:
            self.stdout.write(f'{username} | {password} | {profile}')
        self.stdout.write(
            self.style.WARNING(
                'As senhas sao temporarias e devem ser alteradas no primeiro acesso. '
                'Executar o comando novamente renova todas elas.'
            )
        )
