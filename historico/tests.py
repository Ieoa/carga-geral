import os
import re
from io import StringIO
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from desktop_launcher import (
    LauncherConfigurationError,
    check_database_endpoint,
    configure_environment,
    database_endpoint,
    load_environment_file,
    load_or_create_secret_key,
)

from .models import UserAccess
from .security import create_user_with_temporary_password

TEST_DATABASE_PASSWORD = token_urlsafe(24)
TEST_SECRET_KEY = token_urlsafe(48)
DEFAULT_INSECURE_SECRET_KEY = "-".join(
    ("django", "insecure", "local", "development", "key", "change", "me")
)
EXAMPLE_INSECURE_SECRET_KEY = "-".join(
    ("troque", "por", "uma", "chave", "secreta", "grande", "e", "unica")
)
EXAMPLE_DATABASE_PASSWORD = "-".join(("troque", "a", "senha"))


class AccessSecurityTests(TestCase):
    def test_temporary_password_is_random_and_requires_change(self):
        user, temporary_password = create_user_with_temporary_password(
            username="matricula01",
            first_name="Usuario",
        )

        self.assertTrue(user.check_password(temporary_password))
        self.assertNotIn("matricula01", temporary_password)
        self.assertGreaterEqual(len(temporary_password), 16)
        self.assertTrue(user.access_control.must_change_password)

    def test_user_is_redirected_until_password_is_changed(self):
        user, temporary_password = create_user_with_temporary_password(
            username="matricula02",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("alterar_senha"))

        response = self.client.post(
            reverse("alterar_senha"),
            {
                "old_password": temporary_password,
                "new_password1": "NovaSenhaCorporativa!2026",
                "new_password2": "NovaSenhaCorporativa!2026",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user.refresh_from_db()
        user.access_control.refresh_from_db()
        self.assertTrue(user.check_password("NovaSenhaCorporativa!2026"))
        self.assertFalse(user.access_control.must_change_password)

    def test_management_command_reprovisions_existing_user(self):
        user = User.objects.create_user("matricula03", password="senha-antiga")
        output = StringIO()

        call_command("provisionar_acesso", "matricula03", stdout=output)

        user.refresh_from_db()
        access = UserAccess.objects.get(user=user)
        self.assertFalse(user.check_password("senha-antiga"))
        self.assertTrue(access.must_change_password)
        self.assertIn("Senha temporária:", output.getvalue())

    @override_settings(DEBUG=True)
    def test_demo_command_creates_all_profiles_with_temporary_passwords(self):
        output = StringIO()

        call_command("criar_usuarios_demo", stdout=output)

        text = output.getvalue()
        expected_profiles = {
            "admin_demo": (True, True, None),
            "gestor_demo": (False, False, "GER"),
            "comum_demo": (False, False, "AUX"),
        }
        for username, (is_staff, is_superuser, cargo) in expected_profiles.items():
            user = User.objects.get(username=username)
            password_match = re.search(
                rf"^{username} \| ([^| ]+) \|", text, re.MULTILINE
            )
            self.assertIsNotNone(password_match)
            self.assertTrue(user.check_password(password_match.group(1)))
            self.assertTrue(user.access_control.must_change_password)
            self.assertEqual(user.is_staff, is_staff)
            self.assertEqual(user.is_superuser, is_superuser)
            if cargo:
                self.assertEqual(user.estoque_colaborador.cargo, cargo)

    @override_settings(DEBUG=False)
    def test_demo_command_is_blocked_in_production(self):
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            call_command("criar_usuarios_demo")

    def test_initial_setup_creates_one_random_admin_and_is_idempotent(self):
        first_output = StringIO()
        second_output = StringIO()

        call_command(
            "preparar_acesso_inicial",
            skip_migrate=True,
            stdout=first_output,
        )
        user = User.objects.get(username="admin_inicial")
        password_match = re.search(
            r"^Senha temporaria: (.+)$",
            first_output.getvalue(),
            re.MULTILINE,
        )
        self.assertIsNotNone(password_match)
        self.assertTrue(user.check_password(password_match.group(1)))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.access_control.must_change_password)

        call_command(
            "preparar_acesso_inicial",
            skip_migrate=True,
            stdout=second_output,
        )
        self.assertEqual(User.objects.filter(username="admin_inicial").count(), 1)
        self.assertIn("senha preservada", second_output.getvalue())

    def test_initial_setup_promotes_and_authorizes_explicit_existing_user(self):
        user = User.objects.create_user("admin_ad", password="senha-existente")

        call_command(
            "preparar_acesso_inicial",
            username="admin_ad",
            skip_migrate=True,
            promote_existing=True,
        )

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(UserAccess.objects.filter(user=user).exists())


class DesktopLauncherSecurityTests(SimpleTestCase):
    def test_secret_key_is_unique_and_persisted_per_installation(self):
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first_path = Path(first_dir)
            first_secret = load_or_create_secret_key(first_path)

            self.assertEqual(first_secret, load_or_create_secret_key(first_path))
            self.assertNotEqual(
                first_secret, load_or_create_secret_key(Path(second_dir))
            )
            self.assertGreaterEqual(len(first_secret), 50)

    def test_desktop_environment_disables_debug(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch.dict(os.environ, {}, clear=True):
                os.environ["DATABASE_URL"] = (
                    "mysql://usuario:senha@localhost:3306/historico_navios"
                )
                os.environ["DJANGO_SECRET_KEY"] = TEST_SECRET_KEY
                configure_environment(data_dir / "media", data_dir)

                self.assertEqual(os.environ["DEBUG"], "False")
                self.assertEqual(os.environ["DESKTOP_MODE"], "True")
                self.assertGreaterEqual(len(os.environ["DJANGO_SECRET_KEY"]), 50)

    def test_explicit_environment_file_is_loaded_without_overriding_windows(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            environment_path = data_dir / "empresa.env"
            environment_path.write_text(
                "DATABASE_URL=mysql://arquivo:senha@mysql-rede:3307/loggeral\n"
                "DEBUG=True\n"
                "AD_AUTH_ENABLED=True\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "LOGGERAL_ENV_FILE": str(environment_path),
                    "AD_AUTH_ENABLED": "False",
                },
                clear=True,
            ):
                loaded_path = load_environment_file(data_dir)

                self.assertEqual(loaded_path, environment_path.resolve())
                self.assertEqual(
                    os.environ["DATABASE_URL"],
                    "mysql://arquivo:senha@mysql-rede:3307/loggeral",
                )
                self.assertEqual(os.environ["AD_AUTH_ENABLED"], "False")

    def test_missing_explicit_environment_file_has_clear_error(self):
        with TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "nao-existe.env"
            with patch.dict(
                os.environ,
                {"LOGGERAL_ENV_FILE": str(missing_path)},
                clear=True,
            ):
                with self.assertRaisesMessage(
                    LauncherConfigurationError,
                    "nao foi encontrado",
                ):
                    load_environment_file(Path(temp_dir))

    def test_database_endpoint_accepts_mysql_and_hides_password_on_failure(self):
        database_url = (
            "mysql://usuario:senha-super-secreta@mysql-rede:3307/historico_navios"
        )
        self.assertEqual(database_endpoint(database_url), ("mysql-rede", 3307))

        with patch(
            "desktop_launcher.socket.create_connection",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaises(LauncherConfigurationError) as context:
                check_database_endpoint(database_url)

        message = str(context.exception)
        self.assertIn("mysql-rede:3307", message)
        self.assertNotIn("senha-super-secreta", message)

    def test_database_endpoint_rejects_non_mysql_database(self):
        with self.assertRaisesMessage(
            LauncherConfigurationError,
            "MySQL ou MariaDB",
        ):
            database_endpoint("postgres://usuario:senha@servidor/banco")


class NetworkDeploymentSettingsTests(SimpleTestCase):
    remote_database = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "historico_navios",
            "USER": "historico_navios",
            "PASSWORD": TEST_DATABASE_PASSWORD,
            "HOST": "mysql-servidor.empresa.local",
            "PORT": "3306",
        }
    }

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES=remote_database,
        ALLOWED_HOSTS=["127.0.0.1", "loggeral-servidor", "192.168.1.50"],
        PUBLIC_BASE_URL="http://192.168.1.50:8000",
        SECRET_KEY=TEST_SECRET_KEY,
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_network_configuration_is_accepted(self):
        output = StringIO()

        call_command("verificar_rede", stdout=output)

        text = output.getvalue()
        self.assertIn("mysql-servidor.empresa.local:3306", text)
        self.assertIn("http://192.168.1.50:8000", text)
        self.assertNotIn(TEST_DATABASE_PASSWORD, text)

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": "historico_navios",
                "PASSWORD": TEST_DATABASE_PASSWORD,
                "HOST": "127.0.0.1",
                "PORT": "3306",
            }
        },
        ALLOWED_HOSTS=["192.168.1.50"],
        PUBLIC_BASE_URL="http://192.168.1.50:8000",
        SECRET_KEY=TEST_SECRET_KEY,
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_network_configuration_rejects_local_database(self):
        with self.assertRaisesMessage(CommandError, "servidor MySQL da rede"):
            call_command("verificar_rede")

    @override_settings(
        DEBUG=True,
        SERVE_MEDIA_LOCALLY=False,
        DATABASES=remote_database,
        ALLOWED_HOSTS=["*"],
        PUBLIC_BASE_URL="http://127.0.0.1:8000",
        SECRET_KEY=DEFAULT_INSECURE_SECRET_KEY,
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_network_configuration_rejects_insecure_values(self):
        with self.assertRaises(CommandError) as context:
            call_command("verificar_rede")

        message = str(context.exception)
        self.assertIn("ALLOWED_HOSTS nao pode usar '*'", message)
        self.assertIn("PUBLIC_BASE_URL deve usar o IP ou nome de rede", message)
        self.assertIn("DEBUG deve ser False", message)
        self.assertIn("SERVE_MEDIA_LOCALLY deve ser True", message)
        self.assertIn("SECURE_SSL_REDIRECT deve ser False", message)
        self.assertIn("SESSION_COOKIE_SECURE e CSRF_COOKIE_SECURE", message)

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES=remote_database,
        ALLOWED_HOSTS=["loggeral-servidor"],
        PUBLIC_BASE_URL="http://192.168.1.50:8000",
        SECRET_KEY=TEST_SECRET_KEY,
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_public_host_must_be_explicitly_allowed(self):
        with self.assertRaisesMessage(CommandError, "listado explicitamente"):
            call_command("verificar_rede")

    @override_settings(
        DEBUG=False,
        SERVE_MEDIA_LOCALLY=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": "historico_navios",
                "PASSWORD": EXAMPLE_DATABASE_PASSWORD,
                "HOST": "mysql-servidor.empresa.local",
                "PORT": "3306",
            }
        },
        ALLOWED_HOSTS=["192.168.1.50"],
        PUBLIC_BASE_URL="http://192.168.1.50:8000",
        SECRET_KEY=EXAMPLE_INSECURE_SECRET_KEY,
        SECURE_SSL_REDIRECT=False,
        SESSION_COOKIE_SECURE=False,
        CSRF_COOKIE_SECURE=False,
    )
    def test_placeholder_credentials_are_rejected(self):
        with self.assertRaises(CommandError) as context:
            call_command("verificar_rede")

        message = str(context.exception)
        self.assertIn("senha do usuario MySQL", message)
        self.assertIn("DJANGO_SECRET_KEY precisa ser uma chave longa", message)
