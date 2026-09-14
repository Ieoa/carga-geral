import os
import secrets
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from decouple import config


APP_NAME = "HistoricoNavios"
HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def resource_path(*parts):
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir.joinpath(*parts)


def app_data_dir():
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    secret_path = data_dir / 'secret_key.txt'
    if secret_path.exists():
        secret_key = secret_path.read_text(encoding='utf-8').strip()
        if len(secret_key) >= 50:
            return secret_key

    secret_key = secrets.token_urlsafe(64)
    secret_path.write_text(secret_key, encoding='utf-8')
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass
    return secret_key


def configure_environment(media_path, data_dir):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", load_or_create_secret_key(data_dir))
    os.environ.setdefault("DEBUG", "False")
    os.environ.setdefault("DESKTOP_MODE", "True")
    database_url = config("DATABASE_URL", default="")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL nao configurada. Defina a conexao MySQL antes de iniciar, "
            "por exemplo: mysql://usuario:senha@servidor:3306/historico_navios"
        )
    os.environ["DATABASE_URL"] = database_url
    os.environ["MEDIA_ROOT"] = str(media_path)
    os.environ.setdefault("ALLOWED_HOSTS", f"{HOST},localhost")
    os.environ.setdefault("PUBLIC_BASE_URL", f"http://{HOST}:{DEFAULT_PORT}")
    os.environ.setdefault("SECURE_SSL_REDIRECT", "False")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "False")
    os.environ.setdefault("CSRF_COOKIE_SECURE", "False")
    os.environ.setdefault("SECURE_HSTS_SECONDS", "0")


def migrate_database():
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=0)
    call_command("preparar_acesso_inicial", skip_migrate=True, verbosity=1)


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
    from django.core.management import execute_from_command_line

    execute_from_command_line(["desktop_launcher", "runserver", f"{HOST}:{port}", "--noreload"])


def main():
    data_dir = app_data_dir()
    media_path = copy_initial_data(data_dir)
    port = find_free_port()
    configure_environment(media_path, data_dir)
    os.environ["PUBLIC_BASE_URL"] = f"http://{HOST}:{port}"

    migrate_database()

    url = f"http://{HOST}:{port}/"
    print(f"{APP_NAME} iniciado em {url}")
    print(f"Dados locais em: {data_dir}")
    print("Feche esta janela para encerrar o sistema.")
    open_browser_when_ready(url)
    run_server(port)


if __name__ == "__main__":
    main()
