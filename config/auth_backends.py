import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars


logger = logging.getLogger(__name__)


class ActiveDirectoryBackend(BaseBackend):
    """Autentica no AD e sincroniza os dados basicos no usuario Django."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not settings.AD_AUTH_ENABLED or not username or not password:
            return None

        required = {
            "AD_SERVER_URI": settings.AD_SERVER_URI,
            "AD_BIND_DN": settings.AD_BIND_DN,
            "AD_BIND_PASSWORD": settings.AD_BIND_PASSWORD,
            "AD_USER_SEARCH_BASE": settings.AD_USER_SEARCH_BASE,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            logger.error("Configuracao AD incompleta: %s", ", ".join(missing))
            return None

        parsed = urlsplit(settings.AD_SERVER_URI)
        use_ssl = parsed.scheme.lower() == "ldaps"
        host = parsed.hostname or settings.AD_SERVER_URI
        port = parsed.port or (636 if use_ssl else 389)
        server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL)

        try:
            with self._connection(
                server,
                settings.AD_BIND_DN,
                settings.AD_BIND_PASSWORD,
                start_tls=settings.AD_START_TLS and not use_ssl,
            ) as service_connection:
                ldap_filter = settings.AD_USER_FILTER.format(
                    username=escape_filter_chars(username)
                )
                found = service_connection.search(
                    settings.AD_USER_SEARCH_BASE,
                    ldap_filter,
                    search_scope=SUBTREE,
                    attributes=["sAMAccountName", "givenName", "sn", "mail"],
                    size_limit=2,
                )
                if not found or len(service_connection.entries) != 1:
                    return None
                entry = service_connection.entries[0]
                user_dn = entry.entry_dn
                attributes = entry.entry_attributes_as_dict

            with self._connection(
                server,
                user_dn,
                password,
                start_tls=settings.AD_START_TLS and not use_ssl,
            ):
                pass

        except LDAPException as exc:
            logger.warning("Falha de autenticacao no Active Directory: %s", exc)
            return None

        defaults = {
            "first_name": self._first(attributes.get("givenName")),
            "last_name": self._first(attributes.get("sn")),
            "email": self._first(attributes.get("mail")),
            "is_active": True,
        }
        lookup_username = self._first(attributes.get("sAMAccountName")) or username
        user = User.objects.filter(username__iexact=lookup_username).first()
        if user is None and not settings.AD_CREATE_USERS:
            return None
        created = user is None
        if created:
            user = User.objects.create(username=lookup_username, **defaults)

        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        elif settings.AD_ALWAYS_UPDATE_USER:
            changed = []
            for field, value in defaults.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)
            if changed:
                user.save(update_fields=changed)
        return user

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()

    @staticmethod
    def _connection(server, username, password, *, start_tls):
        connection = Connection(
            server,
            user=username,
            password=password,
            auto_bind=False,
            raise_exceptions=True,
        )
        connection.open()
        if start_tls:
            connection.start_tls()
        connection.bind()
        return connection

    @staticmethod
    def _first(value):
        if isinstance(value, (list, tuple)):
            return str(value[0]) if value else ""
        return str(value or "")
