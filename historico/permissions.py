from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

MANAGER_CARGOS = {"GER", "CORD", "SUP"}


def _cargo_from_related(user):
    for attr in ("estoque_colaborador", "colaborador"):
        colaborador = getattr(user, attr, None)
        cargo = getattr(colaborador, "cargo", None)
        if cargo:
            return cargo
    return ""


def profile_role(user):
    if not user.is_authenticated:
        return "anonymous"
    if user.is_superuser or user.is_staff:
        return "admin"
    if _cargo_from_related(user) in MANAGER_CARGOS:
        return "manager"
    return "employee"


def is_admin(user):
    return profile_role(user) == "admin"


def is_manager(user):
    return profile_role(user) in {"admin", "manager"}


def can_manage_users(user):
    return is_admin(user)


def can_delete_records(user):
    return is_manager(user)


def can_edit_object(user, obj):
    if is_manager(user):
        return True
    owner = getattr(obj, "criado_por", None)
    return bool(owner and owner == user)


def filter_owned_queryset(user, queryset):
    if is_manager(user):
        return queryset
    return queryset.filter(criado_por=user)


def filter_midia_queryset(user, queryset):
    if is_manager(user):
        return queryset
    return queryset.filter(navio__criado_por=user)


def role_context(request):
    user = request.user
    return {
        "perfil_acesso": profile_role(user),
        "is_admin_profile": is_admin(user),
        "is_manager_profile": is_manager(user),
        "can_manage_users": can_manage_users(user),
        "can_delete_records": can_delete_records(user),
    }


def permission_required(check, message="Você não tem permissão para acessar esta página."):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if check(request.user):
                return view_func(request, *args, **kwargs)
            messages.error(request, message)
            return redirect("dashboard")

        return wrapped

    return decorator
