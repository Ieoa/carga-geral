from pathlib import Path
from io import StringIO
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core.management import call_command
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
                configure_environment(data_dir / 'db.sqlite3', data_dir / 'media', data_dir)

                self.assertEqual(os.environ['DEBUG'], 'False')
                self.assertEqual(os.environ['DESKTOP_MODE'], 'True')
                self.assertGreaterEqual(len(os.environ['DJANGO_SECRET_KEY']), 50)
