from uuid import UUID
import json
from rest_framework.renderers import JSONRenderer
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from chats.access import get_conversation_or_404
from chats.events import chat_group_name
from chats.models import ChatMessage
from chats.api.v1.serializers import ChatMessageSerializer
from chats.ws_auth import authenticate_access_token


@database_sync_to_async
def can_access_conversation(*, workspace_slug, conversation_id, user):
    try:
        get_conversation_or_404(
            workspace_slug=workspace_slug,
            conversation_id=conversation_id,
            actor=user,
        )
    except (Http404, PermissionDenied):
        return False

    return True


@database_sync_to_async
def get_message_payload(*, conversation_id, message_id):
    message = (
        ChatMessage.objects
        .filter(
            pk=message_id,
            conversation_id=conversation_id,
        )
        .select_related("sender", "reply_to")
        .prefetch_related("attachments")
        .first()
    )

    if message is None:
        return None

    return json.loads(
        JSONRenderer().render(
            ChatMessageSerializer(message).data
        )
    )


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.joined_group = False

        user = self.scope.get("user")

        if (
            user is None
            or not user.is_authenticated
            or not user.is_active
        ):
            await self.close(code=4401)
            return

        self.workspace_slug = self.scope["url_route"]["kwargs"][
            "workspace_slug"
        ]
        raw_conversation_id = self.scope["url_route"]["kwargs"][
            "conversation_id"
        ]

        try:
            self.conversation_id = UUID(str(raw_conversation_id))
        except (ValueError, TypeError, AttributeError):
            await self.close(code=4404)
            return

        allowed = await can_access_conversation(
            workspace_slug=self.workspace_slug,
            conversation_id=self.conversation_id,
            user=user,
        )

        if not allowed:
            await self.close(code=4403)
            return

        self.group_name = chat_group_name(self.conversation_id)

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        self.joined_group = True

        # Never echo the JWT as an accepted subprotocol.
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "joined_group", False):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )
            self.joined_group = False

    async def receive_json(self, content, **kwargs):
        # Mutations must use REST.
        await self.close(code=4400)

    async def chat_event(self, event):
        protocols = self.scope.get("subprotocols", [])

        if len(protocols) != 2 or protocols[0] != "jwt":
            await self.close(code=4401)
            return

        # Revalidate JWT, UserSession and user status.
        user = await authenticate_access_token(protocols[1])

        if not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return

        allowed = await can_access_conversation(
            workspace_slug=self.workspace_slug,
            conversation_id=self.conversation_id,
            user=user,
        )

        if not allowed:
            await self.close(code=4403)
            return

        event_type = event.get("event_type")

        if event_type not in {
            "message.created",
            "message.updated",
            "message.deleted",
        }:
            return

        try:
            message_id = UUID(str(event["message_id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            return

        payload = await get_message_payload(
            conversation_id=self.conversation_id,
            message_id=message_id,
        )

        if payload is None:
            return

        await self.send_json({
            "type": event_type,
            "message": payload,
        })
