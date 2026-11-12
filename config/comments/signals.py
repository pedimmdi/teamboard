from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CommentAttachment
from .storage import attachment_storage


@receiver(post_delete, sender=CommentAttachment)
def remove_attachment_file(sender, instance, using, **kwargs):
    key = instance.storage_key
    transaction.on_commit(lambda: attachment_storage().delete(key), using=using, robust=True)
