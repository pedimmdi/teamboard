
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


logger = logging.getLogger(__name__)


def chat_group_name(conversation_id):
    return f"chat.{conversation_id.hex}"


def publish_chat_event(*, conversation_id, event_type, message_id):
    channel_layer = get_channel_layer()

    if channel_layer is None:
        logger.warning(
            "Chat event skipped: channel layer unavailable."
        )
        return

    async_to_sync(channel_layer.group_send)(
        chat_group_name(conversation_id),
        {
            "type": "chat.event",
            "event_type": event_type,
            "message_id": str(message_id),
        },
    )


def schedule_chat_event(*, conversation_id, event_type, message_id):
    transaction.on_commit(
        lambda: publish_chat_event(
            conversation_id=conversation_id,
            event_type=event_type,
            message_id=message_id,
        ),
        robust=True,
    )
