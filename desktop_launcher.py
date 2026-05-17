import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


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
    db_target = data_dir / "db.sqlite3"
    db_source = resource_path("db.sqlite3")
    if not db_target.exists() and db_source.exists():
        shutil.copy2(db_source, db_target)

    media_target = data_dir / "media"
    media_source = resource_path("media")
    if not media_target.exists():
        if media_source.exists():
            shutil.copytree(media_source, media_target)
        else:
            media_target.mkdir(parents=True, exist_ok=True)

    return db_target, media_target


def find_free_port(start_port=DEFAULT_PORT):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError("Nenhuma porta local livre encontrada entre 8000 e 8049.")


def configure_environment(db_path, media_path):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", "local-desktop-secret-key-change-for-shared-installs-1234567890")
    os.environ.setdefault("DEBUG", "True")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
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
    db_path, media_path = copy_initial_data(data_dir)
    port = find_free_port()
    configure_environment(db_path, media_path)
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
