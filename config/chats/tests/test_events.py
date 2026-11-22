
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from chats.events import (
    chat_group_name,
    schedule_chat_event,
)


class ChatEventTests(TestCase):
    def test_group_name_uses_conversation_uuid(self):
        conversation_id = uuid4()

        self.assertEqual(
            chat_group_name(conversation_id),
            f"chat.{conversation_id.hex}",
        )

    @patch("chats.events.publish_chat_event")
    def test_event_published_after_commit(self, publish):
        conversation_id = uuid4()
        message_id = uuid4()

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            schedule_chat_event(
                conversation_id=conversation_id,
                event_type="message.created",
                message_id=message_id,
            )

            publish.assert_not_called()

        self.assertEqual(len(callbacks), 1)

        publish.assert_called_once_with(
            conversation_id=conversation_id,
            event_type="message.created",
            message_id=message_id,
        )

    @patch("chats.events.publish_chat_event")
    def test_event_not_published_after_rollback(self, publish):
        conversation_id = uuid4()
        message_id = uuid4()

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                from django.db import transaction

                with transaction.atomic():
                    schedule_chat_event(
                        conversation_id=conversation_id,
                        event_type="message.created",
                        message_id=message_id,
                    )
                    raise ValueError("Force rollback")
            except ValueError:
                pass

        self.assertEqual(len(callbacks), 0)
        publish.assert_not_called()

    @patch("chats.events.get_channel_layer")
    @patch("chats.events.async_to_sync")
    def test_publish_sends_expected_group_event(
        self,
        async_to_sync_mock,
        get_layer_mock,
    ):
        from chats.events import publish_chat_event

        conversation_id = uuid4()
        message_id = uuid4()

        layer = get_layer_mock.return_value

        publish_chat_event(
            conversation_id=conversation_id,
            event_type="message.created",
            message_id=message_id,
        )

        async_to_sync_mock.assert_called_once_with(
            layer.group_send
        )

        async_to_sync_mock.return_value.assert_called_once_with(
            f"chat.{conversation_id.hex}",
            {
                "type": "chat.event",
                "event_type": "message.created",
                "message_id": str(message_id),
            },
        )
