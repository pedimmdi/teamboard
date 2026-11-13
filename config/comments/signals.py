import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CommentAttachment
from .storage import attachment_storage

logger = logging.getLogger(__name__)


def delete_file(key):
    try:
        attachment_storage().delete(key)
    except OSError:
        logger.exception("Unable to delete comment attachment %s; retry via cleanup_comment_attachments", key)


@receiver(post_delete, sender=CommentAttachment)
def remove_attachment_file(sender, instance, using, **kwargs):
    key = instance.storage_key
    transaction.on_commit(lambda: delete_file(key), using=using, robust=True)
