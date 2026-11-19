
import logging

from django.db import transaction

from chats.models import ChatAttachment
from chats.storage import chat_attachment_storage


logger = logging.getLogger(__name__)


def cleanup_deleted_attachment(attachment_id, *, cutoff=None):
    storage = chat_attachment_storage()

    with transaction.atomic():
        queryset = (
            ChatAttachment.objects
            .select_for_update()
            .filter(
                pk=attachment_id,
                message__deleted_at__isnull=False,
            )
        )

        if cutoff is not None:
            queryset = queryset.filter(
                message__deleted_at__lte=cutoff,
            )

        attachment = queryset.first()

        if attachment is None:
            return False

        storage.delete(attachment.storage_key)
        attachment.delete()

    return True
