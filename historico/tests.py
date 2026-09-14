from pathlib import Path
from io import StringIO
import os
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import UserAccess
from .security import create_user_with_temporary_password
from .utils.scraping_praticagem_reduzido import get_navios_cargo_reduzido
from desktop_launcher import configure_environment, load_or_create_secret_key


class PraticagemCacheTests(SimpleTestCase):
    def test_returns_cached_navios_when_request_fails(self):
        with TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "praticagem_navios.json"
            cache_file.write_text(
                '[{"data": "01/01/2026", "hora": "10:00", "navio": "NAVIO TESTE", "tipo_navio": "CARGO SHIP", "terminal": "TECONT1"}]',
                encoding="utf-8",
            )

            with override_settings(MEDIA_ROOT=temp_dir):
                with patch(
                    "historico.utils.scraping_praticagem_reduzido.requests.get",
                    side_effect=requests.RequestException,
                ):
                    navios = get_navios_cargo_reduzido()

        self.assertEqual(navios[0]["navio"], "NAVIO TESTE")


class AccessSecurityTests(TestCase):
    def test_temporary_password_is_random_and_requires_change(self):
        user, temporary_password = create_user_with_temporary_password(
            username='matricula01',
            email='usuario@empresa.com',
            first_name='Usuario',
        )

        self.assertTrue(user.check_password(temporary_password))
        self.assertNotIn('matricula01', temporary_password)
        self.assertGreaterEqual(len(temporary_password), 16)
        self.assertTrue(user.access_control.must_change_password)

    def test_user_is_redirected_until_password_is_changed(self):
        user, temporary_password = create_user_with_temporary_password(
            username='matricula02',
            email='usuario2@empresa.com',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('alterar_senha'))

        response = self.client.post(reverse('alterar_senha'), {
            'old_password': temporary_password,
            'new_password1': 'NovaSenhaCorporativa!2026',
            'new_password2': 'NovaSenhaCorporativa!2026',
        })

        self.assertRedirects(response, reverse('dashboard'))
        user.refresh_from_db()
        user.access_control.refresh_from_db()
        self.assertTrue(user.check_password('NovaSenhaCorporativa!2026'))
        self.assertFalse(user.access_control.must_change_password)

    def test_management_command_reprovisions_existing_user(self):
        user = User.objects.create_user('matricula03', password='senha-antiga')
        output = StringIO()

        call_command('provisionar_acesso', 'matricula03', stdout=output)

        user.refresh_from_db()
        access = UserAccess.objects.get(user=user)
        self.assertFalse(user.check_password('senha-antiga'))
        self.assertTrue(access.must_change_password)
        self.assertIn('Senha temporária:', output.getvalue())

    @override_settings(DEBUG=True)
    def test_demo_command_creates_all_profiles_with_temporary_passwords(self):
        output = StringIO()

        call_command('criar_usuarios_demo', stdout=output)

        text = output.getvalue()
        expected_profiles = {
            'admin_demo': (True, True, None),
            'gestor_demo': (False, False, 'GER'),
            'comum_demo': (False, False, 'AUX'),
        }
        for username, (is_staff, is_superuser, cargo) in expected_profiles.items():
            user = User.objects.get(username=username)
            password_match = re.search(rf'^{username} \| ([^| ]+) \|', text, re.MULTILINE)
            self.assertIsNotNone(password_match)
            self.assertTrue(user.check_password(password_match.group(1)))
            self.assertTrue(user.access_control.must_change_password)
            self.assertEqual(user.is_staff, is_staff)
            self.assertEqual(user.is_superuser, is_superuser)
            if cargo:
                self.assertEqual(user.estoque_colaborador.cargo, cargo)

    @override_settings(DEBUG=False)
    def test_demo_command_is_blocked_in_production(self):
        with self.assertRaisesMessage(CommandError, 'DEBUG=True'):
            call_command('criar_usuarios_demo')

    def test_initial_setup_creates_one_random_admin_and_is_idempotent(self):
        first_output = StringIO()
        second_output = StringIO()

        call_command(
            'preparar_acesso_inicial',
            skip_migrate=True,
            stdout=first_output,
        )
        user = User.objects.get(username='admin_inicial')
        password_match = re.search(
            r'^Senha temporaria: (.+)$',
            first_output.getvalue(),
            re.MULTILINE,
        )
        self.assertIsNotNone(password_match)
        self.assertTrue(user.check_password(password_match.group(1)))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.access_control.must_change_password)

        call_command(
            'preparar_acesso_inicial',
            skip_migrate=True,
            stdout=second_output,
        )
        self.assertEqual(User.objects.filter(username='admin_inicial').count(), 1)
        self.assertIn('senha preservada', second_output.getvalue())


class DesktopLauncherSecurityTests(SimpleTestCase):
    def test_secret_key_is_unique_and_persisted_per_installation(self):
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first_path = Path(first_dir)
            first_secret = load_or_create_secret_key(first_path)

            self.assertEqual(first_secret, load_or_create_secret_key(first_path))
            self.assertNotEqual(first_secret, load_or_create_secret_key(Path(second_dir)))
            self.assertGreaterEqual(len(first_secret), 50)

    def test_desktop_environment_disables_debug(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch.dict(os.environ, {}, clear=True):
                os.environ['DATABASE_URL'] = 'mysql://usuario:senha@localhost:3306/historico_navios'
                configure_environment(data_dir / 'media', data_dir)

                self.assertEqual(os.environ['DEBUG'], 'False')
                self.assertEqual(os.environ['DESKTOP_MODE'], 'True')
                self.assertGreaterEqual(len(os.environ['DJANGO_SECRET_KEY']), 50)


class NetworkDeploymentSettingsTests(SimpleTestCase):
    remote_database = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'historico_navios',
            'USER': 'historico_navios',
            'PASSWORD': 'nao-exibida',
            'HOST': 'mysql-servidor.empresa.local',
            'PORT': '3306',
        }
    }

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES=remote_database,
        ALLOWED_HOSTS=['127.0.0.1', 'loggeral-servidor', '192.168.1.50'],
        PUBLIC_BASE_URL='http://192.168.1.50:8000',
        SECRET_KEY='chave-de-homologacao-segura-e-diferente-do-valor-padrao',
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_network_configuration_is_accepted(self):
        output = StringIO()

        call_command('verificar_rede', stdout=output)

        text = output.getvalue()
        self.assertIn('mysql-servidor.empresa.local:3306', text)
        self.assertIn('http://192.168.1.50:8000', text)
        self.assertNotIn('nao-exibida', text)

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'historico_navios',
                'PASSWORD': 'senha-configurada',
                'HOST': '127.0.0.1',
                'PORT': '3306',
            }
        },
        ALLOWED_HOSTS=['192.168.1.50'],
        PUBLIC_BASE_URL='http://192.168.1.50:8000',
        SECRET_KEY='chave-de-homologacao-segura-e-diferente-do-valor-padrao',
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_network_configuration_rejects_local_database(self):
        with self.assertRaisesMessage(CommandError, 'servidor MySQL da rede'):
            call_command('verificar_rede')

    @override_settings(
        DEBUG=True,
        SERVE_MEDIA_LOCALLY=False,
        DATABASES=remote_database,
        ALLOWED_HOSTS=['*'],
        PUBLIC_BASE_URL='http://127.0.0.1:8000',
        SECRET_KEY='django-insecure-local-development-key-change-me',
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_network_configuration_rejects_insecure_values(self):
        with self.assertRaises(CommandError) as context:
            call_command('verificar_rede')

        message = str(context.exception)
        self.assertIn("ALLOWED_HOSTS nao pode usar '*'", message)
        self.assertIn('PUBLIC_BASE_URL deve usar o IP ou nome de rede', message)
        self.assertIn('DEBUG deve ser False', message)
        self.assertIn('SERVE_MEDIA_LOCALLY deve ser True', message)
        self.assertIn('SECURE_SSL_REDIRECT deve ser False', message)
        self.assertIn('SESSION_COOKIE_SECURE e CSRF_COOKIE_SECURE', message)

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES=remote_database,
        ALLOWED_HOSTS=['loggeral-servidor'],
        PUBLIC_BASE_URL='http://192.168.1.50:8000',
        SECRET_KEY='chave-de-homologacao-segura-e-diferente-do-valor-padrao',
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_public_host_must_be_explicitly_allowed(self):
        with self.assertRaisesMessage(CommandError, 'listado explicitamente'):
            call_command('verificar_rede')

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'historico_navios',
                'PASSWORD': 'troque-a-senha',
                'HOST': 'mysql-servidor.empresa.local',
                'PORT': '3306',
            }
        },
        ALLOWED_HOSTS=['192.168.1.50'],
        PUBLIC_BASE_URL='http://192.168.1.50:8000',
        SECRET_KEY='troque-por-uma-chave-secreta-grande-e-unica',
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_placeholder_credentials_are_rejected(self):
        with self.assertRaises(CommandError) as context:
            call_command('verificar_rede')

        message = str(context.exception)
        self.assertIn('senha do usuario MySQL', message)
        self.assertIn('DJANGO_SECRET_KEY precisa ser uma chave longa', message)
