from ipaddress import ip_address
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def is_local_host(host):
    normalized = (host or "").strip().strip("[]").lower()
    if normalized in LOCAL_HOSTS:
        return True
    try:
        address = ip_address(normalized)
        return address.is_loopback or address.is_unspecified
    except ValueError:
        return False


def host_is_allowed(host, allowed_hosts):
    normalized = host.lower()
    for entry in allowed_hosts:
        candidate = entry.strip().lower()
        if candidate == normalized:
            return True
        if candidate.startswith(".") and (
            normalized == candidate[1:] or normalized.endswith(candidate)
        ):
            return True
    return False


class Command(BaseCommand):
    help = "Valida a configuracao do LOGGERAL para homologacao na rede corporativa."

    def handle(self, *args, **options):
        errors = []
        database = settings.DATABASES["default"]
        engine = database.get("ENGINE", "")
        database_host = database.get("HOST", "")
        database_port = database.get("PORT") or "3306"
        database_password = database.get("PASSWORD", "")

        if engine != "django.db.backends.mysql":
            errors.append("DATABASE_URL deve usar obrigatoriamente o backend MySQL.")
        if is_local_host(database_host):
            errors.append(
                "DATABASE_URL deve apontar para o servidor MySQL da rede, nao para localhost."
            )
        if not database_password or database_password == "troque-a-senha":
            errors.append("A senha do usuario MySQL ainda nao foi configurada.")

        allowed_hosts = list(settings.ALLOWED_HOSTS)
        if "*" in allowed_hosts:
            errors.append("ALLOWED_HOSTS nao pode usar '*' no teste corporativo.")

        public_url = settings.PUBLIC_BASE_URL.strip().rstrip("/")
        try:
            parsed_url = urlsplit(public_url)
            public_port = parsed_url.port
        except ValueError:
            parsed_url = urlsplit("")
            public_port = None

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            errors.append("PUBLIC_BASE_URL deve ser uma URL HTTP ou HTTPS completa.")
        elif is_local_host(parsed_url.hostname):
            errors.append(
                "PUBLIC_BASE_URL deve usar o IP ou nome de rede do servidor LOGGERAL."
            )
        else:
            expected_port = 443 if parsed_url.scheme == "https" else 8000
            effective_port = public_port or (443 if parsed_url.scheme == "https" else 80)
            if effective_port != expected_port:
                errors.append(
                    f"PUBLIC_BASE_URL deve usar a porta {expected_port} neste modo de teste."
                )
            if not host_is_allowed(parsed_url.hostname, allowed_hosts):
                errors.append(
                    "O host de PUBLIC_BASE_URL precisa estar listado explicitamente em "
                    "ALLOWED_HOSTS."
                )

        if parsed_url.scheme == "http" and settings.SECURE_SSL_REDIRECT:
            errors.append(
                "SECURE_SSL_REDIRECT deve ser False enquanto PUBLIC_BASE_URL usar HTTP."
            )
        if parsed_url.scheme == "http" and (
            settings.SESSION_COOKIE_SECURE or settings.CSRF_COOKIE_SECURE
        ):
            errors.append(
                "SESSION_COOKIE_SECURE e CSRF_COOKIE_SECURE devem ser False no teste HTTP."
            )

        if settings.DEBUG:
            errors.append("DEBUG deve ser False para o teste na rede corporativa.")
        if not settings.SERVE_MEDIA_LOCALLY:
            errors.append(
                "SERVE_MEDIA_LOCALLY deve ser True durante a homologacao em rede."
            )
        insecure_secret_keys = {
            "django-insecure-local-development-key-change-me",
            "troque-por-uma-chave-secreta-grande-e-unica",
        }
        if settings.SECRET_KEY in insecure_secret_keys or len(settings.SECRET_KEY) < 40:
            errors.append("DJANGO_SECRET_KEY precisa ser uma chave longa, unica e nao padrao.")

        if settings.AD_AUTH_ENABLED:
            ad_url = urlsplit(settings.AD_SERVER_URI)
            if ad_url.scheme not in {"ldap", "ldaps"} or not ad_url.hostname:
                errors.append("AD_SERVER_URI deve ser uma URL ldap:// ou ldaps:// valida.")
            if ad_url.scheme == "ldap" and not settings.AD_START_TLS:
                errors.append("Active Directory deve usar LDAPS ou AD_START_TLS=True.")
            required_ad = {"AD_SERVER_URI": settings.AD_SERVER_URI}
            if settings.AD_DIRECT_BIND:
                required_ad["AD_DOMAIN"] = settings.AD_DOMAIN
            else:
                required_ad.update(
                    {
                        "AD_BIND_DN": settings.AD_BIND_DN,
                        "AD_BIND_PASSWORD": settings.AD_BIND_PASSWORD,
                        "AD_USER_SEARCH_BASE": settings.AD_USER_SEARCH_BASE,
                    }
                )
            missing_ad = [name for name, value in required_ad.items() if not value]
            if missing_ad:
                errors.append("Configuracao AD incompleta: " + ", ".join(missing_ad) + ".")

        if errors:
            formatted = "\n- ".join(errors)
            raise CommandError("Configuracao de rede invalida:\n- " + formatted)

        self.stdout.write(f"Servidor MySQL remoto: {database_host}:{database_port}")
        self.stdout.write(f"Endereco para os usuarios: {public_url}")
        if parsed_url.scheme == "http":
            self.stdout.write(self.style.WARNING(
                "HTTP deve ser usado somente na homologacao isolada. Para credenciais, AD e camera do QR Code, prefira HTTPS."
            ))
        if not database.get("OPTIONS", {}).get("ssl"):
            self.stdout.write(self.style.WARNING(
                "Conexao MySQL sem CA TLS configurada. Confirme com a TI se a rede exige criptografia."
            ))
        if settings.EMAIL_BACKEND.endswith(("console.EmailBackend", "dummy.EmailBackend")):
            self.stdout.write(self.style.WARNING(
                "O backend de e-mail atual nao entrega mensagens; avisos permanecerao bloqueados ate configurar SMTP."
            ))
        self.stdout.write(
            self.style.SUCCESS("Configuracao de homologacao em rede validada.")
        )
