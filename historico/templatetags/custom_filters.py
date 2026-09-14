import os

from django import template

register = template.Library()

@register.filter
def basename(value):
    """Retorna apenas o nome do arquivo sem o caminho"""
    return os.path.basename(value)


@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return None


@register.filter
def audit_value(value, key):
    if isinstance(value, dict):
        result = value.get(key)
        return result if result not in (None, "") else "vazio"
    if key == "to":
        return value if value not in (None, "") else "vazio"
    return "vazio"
