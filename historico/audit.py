from django.forms.models import model_to_dict

from .models import AuditLog


IGNORED_FIELDS = {"id", "password", "last_login"}


def snapshot(instance):
    data = model_to_dict(instance)
    return {key: _stringify(value) for key, value in data.items() if key not in IGNORED_FIELDS}


def diff(before, after):
    changes = {}
    for key in sorted(set(before) | set(after)):
        if key in IGNORED_FIELDS:
            continue
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes[key] = {"from": old, "to": new}
    return changes


def log_action(user, instance, action, changes=None):
    if not user or not user.is_authenticated:
        return
    from .permissions import profile_role

    AuditLog.objects.create(
        user=user,
        actor_role=profile_role(user),
        action=action,
        app_label=instance._meta.app_label,
        model_name=instance._meta.model_name,
        object_pk=str(instance.pk),
        object_repr=str(instance),
        changes=changes or {},
    )


def _stringify(value):
    if isinstance(value, (list, tuple)):
        return [_stringify(item) for item in value]
    return "" if value is None else str(value)
