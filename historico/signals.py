from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import DocumentoNavio, FotoVideoNavio


def _delete_after_commit(field_file):
    if field_file and field_file.name:
        storage = field_file.storage
        name = field_file.name
        transaction.on_commit(lambda: storage.delete(name))


def _remember_replaced_file(sender, instance, field_name):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).only(field_name).first()
    if previous:
        old_file = getattr(previous, field_name)
        new_file = getattr(instance, field_name)
        if old_file and old_file.name != getattr(new_file, "name", ""):
            instance._file_to_delete_after_save = old_file


@receiver(pre_save, sender=FotoVideoNavio)
def cleanup_replaced_media(sender, instance, **kwargs):
    _remember_replaced_file(sender, instance, "arquivo")


@receiver(pre_save, sender=DocumentoNavio)
def cleanup_replaced_document(sender, instance, **kwargs):
    _remember_replaced_file(sender, instance, "arquivo")


@receiver(post_save, sender=FotoVideoNavio)
@receiver(post_save, sender=DocumentoNavio)
def delete_remembered_file(sender, instance, **kwargs):
    old_file = getattr(instance, "_file_to_delete_after_save", None)
    if old_file:
        _delete_after_commit(old_file)
        del instance._file_to_delete_after_save


@receiver(post_delete, sender=FotoVideoNavio)
def cleanup_deleted_media(sender, instance, **kwargs):
    _delete_after_commit(instance.arquivo)


@receiver(post_delete, sender=DocumentoNavio)
def cleanup_deleted_document(sender, instance, **kwargs):
    _delete_after_commit(instance.arquivo)
