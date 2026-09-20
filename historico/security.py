from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import UserAccess

PASSWORD_ALPHABET = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%'


def generate_temporary_password(length=16):
    return get_random_string(length, PASSWORD_ALPHABET)


def create_user_with_temporary_password(*, username, first_name='', last_name=''):
    temporary_password = generate_temporary_password()
    user = User.objects.create_user(
        username=username,
        email='',
        first_name=first_name,
        last_name=last_name,
        password=temporary_password,
    )
    UserAccess.objects.update_or_create(
        user=user,
        defaults={
            'must_change_password': True,
            'temporary_password_created_at': timezone.now(),
            'password_changed_at': None,
        },
    )
    return user, temporary_password


def create_pre_authorized_ad_user(*, username, first_name='', last_name=''):
    """Cria somente a autorização local; a senha permanece exclusivamente no AD."""
    user = User(
        username=username,
        email="",
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    user.set_unusable_password()
    user.save()
    authorize_user_for_ad(user)
    return user


def authorize_user_for_ad(user):
    """Remove credenciais e e-mail locais e mantém apenas a autorização de acesso."""
    changed = []
    if user.has_usable_password():
        user.set_unusable_password()
        changed.append("password")
    if user.email:
        user.email = ""
        changed.append("email")
    if changed:
        user.save(update_fields=changed)
    UserAccess.objects.update_or_create(
        user=user,
        defaults={
            'must_change_password': False,
            'temporary_password_created_at': None,
            'password_changed_at': None,
        },
    )


def find_authorized_user(username):
    """Consulta a lista local antes de qualquer autenticação externa."""
    if not username:
        return None
    return (
        User.objects.select_related("access_control")
        .filter(
            username__iexact=username.strip(),
            is_active=True,
            access_control__isnull=False,
        )
        .first()
    )


def issue_temporary_password(user):
    temporary_password = generate_temporary_password()
    user.set_password(temporary_password)
    user.save(update_fields=['password'])
    UserAccess.objects.update_or_create(
        user=user,
        defaults={
            'must_change_password': True,
            'temporary_password_created_at': timezone.now(),
            'password_changed_at': None,
        },
    )
    return temporary_password
