from hashlib import sha256

from django.conf import settings
from django.core.cache import cache


def _key(request, username):
    address = request.META.get("REMOTE_ADDR", "unknown")
    identity = f"{address}|{(username or '').strip().lower()}"
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"loggeral:login-failures:{digest}"


def is_login_blocked(request, username):
    return int(cache.get(_key(request, username), 0)) >= getattr(settings, "LOGIN_FAILURE_LIMIT", 5)


def register_login_failure(request, username):
    key = _key(request, username)
    timeout = getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", 900)
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def clear_login_failures(request, username):
    cache.delete(_key(request, username))
