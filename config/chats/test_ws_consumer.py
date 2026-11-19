
from unittest.mock import patch
from uuid import uuid4

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

from chats.consumers import ChatConsumer


class FakeUser:
    is_authenticated = True
    is_active = True


class ChatConsumerTests(SimpleTestCase):
    async def test_unauthenticated_user_is_rejected(self):
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            "/ws/chats/test-workspace/"
            f"{uuid4()}/",
        )
        communicator.scope["user"] = None
        communicator.scope["url_route"] = {
            "kwargs": {
                "workspace_slug": "test-workspace",
                "conversation_id": str(uuid4()),
            }
        }

        connected, _ = await communicator.connect()

        self.assertFalse(connected)

        await communicator.disconnect()

    async def test_user_without_conversation_access_is_rejected(self):
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            "/ws/chats/test-workspace/"
            f"{uuid4()}/",
        )
        communicator.scope["user"] = FakeUser()
        communicator.scope["url_route"] = {
            "kwargs": {
                "workspace_slug": "test-workspace",
                "conversation_id": str(uuid4()),
            }
        }

        with patch(
            "chats.consumers.can_access_conversation",
            return_value=False,
        ):
            connected, _ = await communicator.connect()

        self.assertFalse(connected)

        await communicator.disconnect()
