import os
import shutil
import socket
import sqlite3
import sys
import threading
import time
import webbrowser
from pathlib import Path


APP_NAME = "HistoricoNavios"
HOST = "127.0.0.1"
DEFAULT_PORT = 8000
TEST_USERNAMES = ("admin_teste", "gerente_teste", "comum_teste")


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
    elif db_target.exists() and db_source.exists():
        sync_test_users(db_source, db_target)

    media_target = data_dir / "media"
    media_source = resource_path("media")
    if not media_target.exists():
        if media_source.exists():
            shutil.copytree(media_source, media_target)
        else:
            media_target.mkdir(parents=True, exist_ok=True)

    return db_target, media_target


def sync_test_users(db_source, db_target):
    if db_source.resolve() == db_target.resolve():
        return

    source = sqlite3.connect(db_source)
    target = sqlite3.connect(db_target)
    source.row_factory = sqlite3.Row
    target.row_factory = sqlite3.Row

    try:
        target.execute("PRAGMA foreign_keys = ON")
        user_map = {}

        for username in TEST_USERNAMES:
            source_user = source.execute(
                "SELECT * FROM auth_user WHERE username = ?",
                (username,),
            ).fetchone()
            if not source_user:
                continue

            target_user = target.execute(
                "SELECT id FROM auth_user WHERE username = ?",
                (username,),
            ).fetchone()

            if target_user:
                user_map[source_user["id"]] = target_user["id"]
                continue

            columns = [column for column in source_user.keys() if column != "id"]
            placeholders = ", ".join("?" for _ in columns)
            target.execute(
                f"INSERT INTO auth_user ({', '.join(columns)}) VALUES ({placeholders})",
                [source_user[column] for column in columns],
            )
            user_map[source_user["id"]] = target.execute("SELECT last_insert_rowid()").fetchone()[0]

        sync_estoque_colaboradores(source, target, user_map)
        target.commit()
    except sqlite3.Error:
        target.rollback()
    finally:
        source.close()
        target.close()


def sync_estoque_colaboradores(source, target, user_map):
    table_exists = source.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'estoque_colaborador'"
    ).fetchone()
    if not table_exists:
        return

    for source_user_id, target_user_id in user_map.items():
        source_colaborador = source.execute(
            "SELECT * FROM estoque_colaborador WHERE user_id = ?",
            (source_user_id,),
        ).fetchone()
        if not source_colaborador:
            continue

        target_colaborador = target.execute(
            "SELECT id FROM estoque_colaborador WHERE user_id = ?",
            (target_user_id,),
        ).fetchone()
        if target_colaborador:
            continue

        conflict = target.execute(
            """
            SELECT id FROM estoque_colaborador
            WHERE matricula = ? OR cpf = ? OR email = ?
            """,
            (
                source_colaborador["matricula"],
                source_colaborador["cpf"],
                source_colaborador["email"],
            ),
        ).fetchone()
        if conflict:
            continue

        columns = [column for column in source_colaborador.keys() if column != "id"]
        placeholders = ", ".join("?" for _ in columns)
        values = [
            target_user_id if column == "user_id" else source_colaborador[column]
            for column in columns
        ]
        target.execute(
            f"INSERT INTO estoque_colaborador ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )


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
