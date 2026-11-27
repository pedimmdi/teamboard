import asyncio
from datetime import timedelta
from secrets import token_urlsafe

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.db import database_sync_to_async
from chats.models import ChatAttachment, ChatMessage, Conversation
from chats.unread import mark_chat_read
from django.contrib.auth import get_user_model
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    set_token_value,
)
from workspaces.models import Workspace, WorkspaceMembership

from ai_integrations.tests.http import mcp_test_client


@pytest.mark.django_db(transaction=True)
def test_chat_tools_expose_only_current_conversations_and_safe_message_fields():
    accounts = get_user_model().objects
    actor = accounts.create_user(email="chat-actor@example.invalid", is_email_verified=True)
    peer = accounts.create_user(email="chat-peer@example.invalid", is_email_verified=True)
    other = accounts.create_user(email="chat-other@example.invalid", is_email_verified=True)
    workspace = Workspace.objects.create(name="Chat test workspace")
    membership = WorkspaceMembership.objects.create(workspace=workspace, user=actor, role="owner")
    WorkspaceMembership.objects.create(workspace=workspace, user=peer)
    WorkspaceMembership.objects.create(workspace=workspace, user=other)

    def direct_chat(first, second):
        user_low, user_high = sorted((first.pk, second.pk))
        return Conversation.objects.create(
            workspace=workspace, type=Conversation.Type.DIRECT,
            direct_user_low_id=user_low, direct_user_high_id=user_high,
        )

    chat = direct_chat(actor, peer)
    hidden = direct_chat(peer, other)
    long_text = "این متن پیام است. " * 200
    visible = ChatMessage.objects.create(conversation=chat, sender=peer, content=long_text)
    ChatMessage.objects.create(conversation=chat, sender=actor, content="My own reply")
    deleted = ChatMessage.objects.create(
        conversation=chat, sender=peer, content="Deleted fixture", deleted_at=timezone.now()
    )
    ChatMessage.objects.create(conversation=hidden, sender=other, content="Private conversation")
    ChatAttachment.objects.create(
        message=visible, filename="test.txt", size=1, storage_key="private/chat/test-key"
    )
    app = get_application_model().objects.create(
        name="Chat reader", client_type="public", authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1:6274/callback", client_secret="",
    )
    token = token_urlsafe()
    access = get_access_token_model()(
        user=actor, application=app, scope="teamboard.read",
        resource=[settings.MCP_LOCAL_RESOURCE], expires=timezone.now() + timedelta(minutes=5),
    )
    set_token_value(access, token)
    access.save()

    async def check():
        async with mcp_test_client() as client:
            async def call(name, **arguments):
                reply = await client.post(
                    "/mcp",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Authorization": f"Bearer {token}",
                        "MCP-Protocol-Version": "2025-11-25",
                    },
                    json={
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": name, "arguments": {
                            "workspace_slug": workspace.slug, **arguments,
                        }},
                    },
                )
                assert reply.status_code == 200
                return reply.json()["result"]

            result = (await call("teamboard_list_chats"))["structuredContent"]
            assert [row["conversation_id"] for row in result["results"]] == [str(chat.pk)]
            assert result["results"][0]["recipient_id"] == peer.pk
            refused = await call("teamboard_list_chat_messages", conversation_id=str(hidden.pk))
            assert "NOT_FOUND" in refused["content"][0]["text"]
            recent = await call("teamboard_list_chat_messages", conversation_id=str(chat.pk))
            rows = recent["structuredContent"]["results"]
            assert len(rows) == 2
            assert str(deleted.pk) not in {row["message_id"] for row in rows}
            assert rows[1]["message_id"] == str(visible.pk)
            assert rows[1]["content"] == long_text[:2000]
            assert rows[1]["content_truncated"] is True
            assert rows[1]["has_attachments"] is True
            assert "private/chat/test-key" not in str(recent)
            assert "test.txt" not in str(recent)
            attachments = await call("teamboard_list_chat_attachments", conversation_id=str(chat.pk), message_id=str(visible.pk))
            file = attachments["structuredContent"]["attachments"][0]
            assert set(file) == {"id", "filename", "size"}
            assert file["filename"] == "test.txt"
            assert "private/chat/test-key" not in str(attachments)
            denied_file = await call("teamboard_list_chat_attachments", conversation_id=str(hidden.pk), message_id=str(visible.pk))
            assert denied_file["isError"]
            count = await call("teamboard_get_chat_unread_count")
            assert count["structuredContent"] == {"unread_count": 1}
            await database_sync_to_async(mark_chat_read)(
                workspace_slug=workspace.slug, conversation_id=chat.pk, actor=actor, message_id=visible.pk
            )
            count = await call("teamboard_get_chat_unread_count")
            assert count["structuredContent"] == {"unread_count": 0}
            await database_sync_to_async(membership.delete)()
            result = await call("teamboard_list_chats")
            assert "NOT_FOUND" in result["content"][0]["text"]

    asyncio.run(check())
