import logging
import ssl
from contextlib import contextmanager
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.contrib.auth.models import User
from ldap3 import NONE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)


class RegisteredUserModelBackend(ModelBackend):
    """Autenticação local limitada à lista explícita de contas autorizadas."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and hasattr(user, "access_control")

    def get_user(self, user_id):
        user = super().get_user(user_id)
        return user if user is not None and self.user_can_authenticate(user) else None


class ActiveDirectoryBackend(BaseBackend):
    """Autentica no AD somente contas previamente autorizadas no LOGGERAL."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not settings.AD_AUTH_ENABLED or not username or not password:
            return None

        from historico.security import find_authorized_user

        user = find_authorized_user(username)
        if user is None:
            # Defesa em profundidade: não instancia Server nem consulta o AD.
            return None

        direct_bind = settings.AD_DIRECT_BIND
        required = {"AD_SERVER_URI": settings.AD_SERVER_URI}
        if direct_bind:
            required["AD_DOMAIN"] = settings.AD_DOMAIN
        else:
            required.update(
                {
                    "AD_BIND_DN": settings.AD_BIND_DN,
                    "AD_BIND_PASSWORD": settings.AD_BIND_PASSWORD,
                    "AD_USER_SEARCH_BASE": settings.AD_USER_SEARCH_BASE,
                }
            )
        missing = [name for name, value in required.items() if not value]
        if missing:
            logger.error("Configuracao AD incompleta: %s", ", ".join(missing))
            return None

        try:
            parsed = urlsplit(settings.AD_SERVER_URI)
            scheme = parsed.scheme.lower()
            host = parsed.hostname
            port = parsed.port or (636 if scheme == "ldaps" else 389)
        except ValueError:
            logger.error("Active Directory recusado: URI LDAP invalida.")
            return None
        if scheme not in {"ldap", "ldaps"} or not host:
            logger.error("Active Directory recusado: URI LDAP invalida.")
            return None
        use_ssl = scheme == "ldaps"
        use_start_tls = settings.AD_START_TLS and not use_ssl
        if not use_ssl and not use_start_tls:
            logger.error("Active Directory recusado: use LDAPS ou STARTTLS.")
            return None
        tls = Tls(
            validate=ssl.CERT_REQUIRED if settings.AD_TLS_VALIDATE else ssl.CERT_NONE,
            ca_certs_file=settings.AD_CA_CERT_FILE or None,
        )
        server = Server(
            host,
            port=port,
            use_ssl=use_ssl,
            tls=tls,
            connect_timeout=settings.AD_CONNECT_TIMEOUT,
            get_info=NONE,
        )

        try:
            if direct_bind:
                principal = f"{settings.AD_DOMAIN}\\{user.username}"
                with self._connection(
                    server,
                    principal,
                    password,
                    start_tls=use_start_tls,
                ):
                    pass
            else:
                with self._connection(
                    server,
                    settings.AD_BIND_DN,
                    settings.AD_BIND_PASSWORD,
                    start_tls=use_start_tls,
                ) as service_connection:
                    ldap_filter = settings.AD_USER_FILTER.format(
                        username=escape_filter_chars(user.username)
                    )
                    found = service_connection.search(
                        settings.AD_USER_SEARCH_BASE,
                        ldap_filter,
                        search_scope=SUBTREE,
                        attributes=["sAMAccountName"],
                        size_limit=2,
                    )
                    if not found or len(service_connection.entries) != 1:
                        return None
                    entry = service_connection.entries[0]
                    account_name = self._first(
                        entry.entry_attributes_as_dict.get("sAMAccountName")
                    )
                    if account_name.casefold() != user.username.casefold():
                        return None
                    user_dn = entry.entry_dn

                with self._connection(
                    server,
                    user_dn,
                    password,
                    start_tls=use_start_tls,
                ):
                    pass

        except (LDAPException, OSError, KeyError, ValueError):
            logger.warning("Falha de autenticacao no Active Directory.")
            return None

        if user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=["password"])

        from django.utils import timezone

        from historico.models import UserAccess

        UserAccess.objects.filter(user=user).update(
            must_change_password=False,
            temporary_password_created_at=None,
            password_changed_at=timezone.now(),
        )
        return user

    def get_user(self, user_id):
        from historico.security import find_authorized_user

        user = User.objects.filter(pk=user_id).only("username").first()
        return find_authorized_user(user.username) if user else None

    @staticmethod
    @contextmanager
    def _connection(server, username, password, *, start_tls):
        connection = Connection(
            server,
            user=username,
            password=password,
            auto_bind=False,
            raise_exceptions=True,
            receive_timeout=settings.AD_RECEIVE_TIMEOUT,
        )
        try:
            connection.open()
            if start_tls and not connection.start_tls():
                raise LDAPException("StartTLS recusado pelo servidor")
            if not connection.bind():
                raise LDAPException("Credenciais recusadas pelo servidor")
            yield connection
        finally:
            if connection.bound:
                connection.unbind()

    @staticmethod
    def _first(value):
        if isinstance(value, (list, tuple)):
            return str(value[0]) if value else ""
        return str(value or "")
