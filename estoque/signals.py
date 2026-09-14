from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Certificacao, Equipamento


def _delete_after_commit(field_file):
    if field_file and field_file.name:
        storage = field_file.storage
        name = field_file.name
        transaction.on_commit(lambda: storage.delete(name))


def _remember_replaced_files(sender, instance, field_names):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only(*field_names).first()
    if not previous:
        return
    remembered = []
    for field_name in field_names:
        old_file = getattr(previous, field_name)
        new_file = getattr(instance, field_name)
        if old_file and old_file.name != getattr(new_file, "name", ""):
            remembered.append(old_file)
    if remembered:
        instance._files_to_delete_after_save = remembered


@receiver(pre_save, sender=Equipamento)
def cleanup_replaced_equipment_files(sender, instance, **kwargs):
    _remember_replaced_files(sender, instance, ("foto", "qrcode"))


@receiver(pre_save, sender=Certificacao)
def cleanup_replaced_certificate(sender, instance, **kwargs):
    _remember_replaced_files(sender, instance, ("anexo",))


@receiver(post_save, sender=Equipamento)
@receiver(post_save, sender=Certificacao)
def delete_remembered_files(sender, instance, **kwargs):
    old_files = getattr(instance, "_files_to_delete_after_save", [])
    for old_file in old_files:
        _delete_after_commit(old_file)
    if old_files:
        del instance._files_to_delete_after_save


@receiver(post_delete, sender=Equipamento)
def cleanup_deleted_equipment(sender, instance, **kwargs):
    _delete_after_commit(instance.foto)
    _delete_after_commit(instance.qrcode)


@receiver(post_delete, sender=Certificacao)
def cleanup_deleted_certificate(sender, instance, **kwargs):
    _delete_after_commit(instance.anexo)
