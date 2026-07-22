from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import UserAccess


PASSWORD_ALPHABET = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%'


def generate_temporary_password(length=16):
    return get_random_string(length, PASSWORD_ALPHABET)


def create_user_with_temporary_password(*, username, email, first_name='', last_name=''):
    temporary_password = generate_temporary_password()
    user = User.objects.create_user(
        username=username,
        email=email,
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
