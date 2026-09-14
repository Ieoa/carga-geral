import logging
import os
import secrets
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

from decouple import RepositoryEnv

APP_NAME = "HistoricoNavios"
HOST = "127.0.0.1"
DEFAULT_PORT = 8000
ENV_FILE_NAME = ".env"
ENV_OVERRIDE_NAME = "LOGGERAL_ENV_FILE"
LOGGER = logging.getLogger(APP_NAME)


class LauncherConfigurationError(RuntimeError):
    """Erro de configuracao que pode ser apresentado sem expor credenciais."""


def resource_path(*parts):
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir.joinpath(*parts)


def app_data_dir():
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def executable_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def environment_file_candidates(data_dir=None):
    """Retorna locais previsiveis, sem depender da pasta de trabalho atual."""
    candidates = []
    explicit_path = os.environ.get(ENV_OVERRIDE_NAME, "").strip()
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    candidates.append(executable_dir() / ENV_FILE_NAME)
    if data_dir is not None:
        candidates.append(Path(data_dir) / ENV_FILE_NAME)

    unique_candidates = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique_candidates:
            unique_candidates.append(resolved)
    return unique_candidates


def load_environment_file(data_dir=None):
    candidates = environment_file_candidates(data_dir)
    explicit_path = os.environ.get(ENV_OVERRIDE_NAME, "").strip()
    if explicit_path and not candidates[0].is_file():
        raise LauncherConfigurationError(
            f"O arquivo indicado por {ENV_OVERRIDE_NAME} nao foi encontrado: "
            f"{candidates[0]}"
        )

    for candidate in candidates:
        if candidate.is_file():
            repository = RepositoryEnv(str(candidate))
            for key, value in repository.data.items():
                os.environ.setdefault(key, value)
            return candidate
    return None


def copy_initial_data(data_dir):
    media_target = data_dir / "media"
    media_source = resource_path("media")
    if not media_target.exists():
        if media_source.exists():
            shutil.copytree(media_source, media_target)
        else:
            media_target.mkdir(parents=True, exist_ok=True)

    return media_target


def find_free_port(start_port=DEFAULT_PORT):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError("Nenhuma porta local livre encontrada entre 8000 e 8049.")


def load_or_create_secret_key(data_dir):
    secret_path = data_dir / "secret_key.txt"
    if secret_path.exists():
        secret_key = secret_path.read_text(encoding="utf-8").strip()
        if len(secret_key) >= 50:
            return secret_key

    secret_key = secrets.token_urlsafe(64)
    secret_path.write_text(secret_key, encoding="utf-8")
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass
    return secret_key


def configure_environment(media_path, data_dir):
    environment_path = load_environment_file(data_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", load_or_create_secret_key(data_dir))
    # O executavel nunca deve herdar o modo de desenvolvimento do arquivo .env.
    os.environ["DEBUG"] = "False"
    os.environ["DESKTOP_MODE"] = "True"
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        expected_path = environment_file_candidates(data_dir)[0]
        raise LauncherConfigurationError(
            "A conexao MySQL nao foi configurada. Crie um arquivo .env ao lado "
            f"do executavel ({expected_path}) e defina DATABASE_URL."
        )
    os.environ["DATABASE_URL"] = database_url
    os.environ["MEDIA_ROOT"] = str(media_path)
    os.environ.setdefault("ALLOWED_HOSTS", f"{HOST},localhost")
    os.environ.setdefault("PUBLIC_BASE_URL", f"http://{HOST}:{DEFAULT_PORT}")
    os.environ.setdefault("SECURE_SSL_REDIRECT", "False")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "False")
    os.environ.setdefault("CSRF_COOKIE_SECURE", "False")
    os.environ.setdefault("SECURE_HSTS_SECONDS", "0")
    return environment_path


def database_endpoint(database_url):
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"mysql", "mysql2"}:
        raise LauncherConfigurationError(
            "DATABASE_URL deve apontar para um servidor MySQL ou MariaDB."
        )
    if not parsed.hostname:
        raise LauncherConfigurationError(
            "DATABASE_URL nao informa o endereco do servidor MySQL."
        )
    try:
        port = parsed.port or 3306
    except ValueError as error:
        raise LauncherConfigurationError(
            "A porta informada em DATABASE_URL nao e valida."
        ) from error
    return parsed.hostname, port


def check_database_endpoint(database_url, timeout=5):
    host, port = database_endpoint(database_url)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return host, port
    except OSError as error:
        raise LauncherConfigurationError(
            "Nao foi possivel conectar ao servidor MySQL "
            f"{host}:{port}. Verifique se o servidor esta ligado, se o endereco "
            "esta correto e se a porta foi liberada no firewall/rede."
        ) from error


def migrate_database():
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=0)
    call_command("preparar_acesso_inicial", skip_migrate=True, verbosity=1)
    call_command("verificar_banco", verbosity=1)
    call_command("verificar_insight", verbosity=1)


def open_browser_when_ready(url):
    def worker():
        for _ in range(50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if sock.connect_ex((HOST, int(url.rsplit(":", 1)[1].rstrip("/")))) == 0:
                    webbrowser.open(url)
                    return
            time.sleep(0.2)

    threading.Thread(target=worker, daemon=True).start()


def run_server(port):
    from waitress import serve

    from config.wsgi import application

    serve(application, host=HOST, port=port, threads=4)


def configure_logging(data_dir):
    log_path = data_dir / "loggeral.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
        force=True,
    )
    return log_path


def startup_error_message(error, data_dir, log_path):
    if isinstance(error, LauncherConfigurationError):
        reason = str(error)
    else:
        error_text = str(error).lower()
        if "access denied" in error_text or "(1045" in error_text:
            reason = (
                "O servidor MySQL recusou o usuario ou a senha configurados. "
                "Confirme a credencial com a equipe de TI."
            )
        elif "unknown database" in error_text or "(1049" in error_text:
            reason = (
                "O servidor MySQL respondeu, mas o banco historico_navios nao existe. "
                "Solicite a criacao do banco antes da primeira execucao."
            )
        else:
            reason = "Ocorreu uma falha durante a inicializacao do LOGGERAL."

    config_path = executable_dir() / ENV_FILE_NAME
    return (
        f"LOGGERAL nao pode iniciar.\n\n{reason}\n\n"
        f"Configuracao esperada: {config_path}\n"
        "Use o arquivo loggeral.env.example como modelo.\n\n"
        f"Log tecnico: {log_path}\n"
        f"Dados locais: {data_dir}"
    )


def show_error(message):
    print(message, file=sys.stderr)
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "LOGGERAL - erro", 0x10)
        except (AttributeError, OSError):
            pass


def main():
    data_dir = app_data_dir()
    log_path = configure_logging(data_dir)
    media_path = copy_initial_data(data_dir)
    try:
        port = find_free_port()
        environment_path = configure_environment(media_path, data_dir)
        os.environ["PUBLIC_BASE_URL"] = f"http://{HOST}:{port}"
        database_host, database_port = check_database_endpoint(
            os.environ["DATABASE_URL"]
        )
        LOGGER.info(
            "Configuracao carregada de %s; MySQL em %s:%s.",
            environment_path or "variaveis do Windows",
            database_host,
            database_port,
        )

        migrate_database()

        url = f"http://{HOST}:{port}/"
        print(f"{APP_NAME} iniciado em {url}")
        print(f"Dados locais em: {data_dir}")
        print("Feche esta janela para encerrar o sistema.")
        open_browser_when_ready(url)
        run_server(port)
    except Exception as error:
        LOGGER.exception("Falha ao iniciar o LOGGERAL")
        show_error(startup_error_message(error, data_dir, log_path))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
