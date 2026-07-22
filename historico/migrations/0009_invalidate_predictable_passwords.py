from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


def invalidate_predictable_passwords(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAccess = apps.get_model('historico', 'UserAccess')
    HistoricoColaborador = apps.get_model('historico', 'Colaborador')
    EstoqueColaborador = apps.get_model('estoque', 'Colaborador')

    user_ids = set(
        HistoricoColaborador.objects.exclude(user_id=None).values_list('user_id', flat=True)
    )
    user_ids.update(
        EstoqueColaborador.objects.exclude(user_id=None).values_list('user_id', flat=True)
    )

    for user in User.objects.filter(pk__in=user_ids):
        user.password = make_password(None)
        user.save(update_fields=['password'])
        UserAccess.objects.update_or_create(
            user_id=user.pk,
            defaults={
                'must_change_password': True,
                'temporary_password_created_at': timezone.now(),
            },
        )

    # Esta credencial foi publicada em uma versão anterior da documentação.
    User.objects.filter(username='admin').update(password=make_password(None))


class Migration(migrations.Migration):
    dependencies = [
        ('estoque', '0016_certificacao_ativa_certificacao_atualizado_por_and_more'),
        ('historico', '0008_useraccess'),
    ]

    operations = [
        migrations.RunPython(invalidate_predictable_passwords, migrations.RunPython.noop),
    ]
