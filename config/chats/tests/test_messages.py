
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from chats.models import ChatMessage
from chats.services import (
    get_or_create_direct_chat,
    create_chat_message,
    update_chat_message,
    delete_chat_message,
    get_chat_messages,
)
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatMessageServiceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="chat-alice@example.com",
            password="Strong-password-2026!",
        )
        self.bob = User.objects.create_user(
            email="chat-bob@example.com",
            password="Strong-password-2026!",
        )
        self.charlie = User.objects.create_user(
            email="chat-charlie@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Message Test Workspace",
        )

        for user, role in (
            (self.alice, WorkspaceMembership.Role.OWNER),
            (self.bob, WorkspaceMembership.Role.MEMBER),
            (self.charlie, WorkspaceMembership.Role.ADMIN),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.conversation = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.bob,
            actor=self.alice,
        )

    def create_message(self, *, actor=None, content="Hello", reply_to=None):
        return create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.conversation.pk,
            actor=actor or self.alice,
            content=content,
            reply_to=reply_to,
        )

    def test_create_reply_and_edit(self):
        original = self.create_message(content="  Hello Bob  ")
        self.assertEqual(original.content, "Hello Bob")

        reply = self.create_message(
            actor=self.bob,
            content="Hi Alice",
            reply_to=original.pk,
        )
        self.assertEqual(reply.reply_to_id, original.pk)

        updated = update_chat_message(
            workspace_slug=self.workspace.slug,
            message_id=original.pk,
            actor=self.alice,
            content="Updated hello",
        )
        self.assertEqual(updated.content, "Updated hello")
        self.assertIsNotNone(updated.edited_at)

    def test_non_participant_cannot_read_or_send(self):
        with self.assertRaises(Http404):
            self.create_message(
                actor=self.charlie,
                content="Unauthorized",
            )

        with self.assertRaises(Http404):
            list(get_chat_messages(
                workspace_slug=self.workspace.slug,
                conversation_id=self.conversation.pk,
                actor=self.charlie,
            ))

    def test_only_sender_can_edit_or_delete(self):
        message = self.create_message()

        with self.assertRaises(PermissionDenied):
            update_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.bob,
                content="Changed",
            )

        with self.assertRaises(PermissionDenied):
            delete_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.bob,
            )

        message.refresh_from_db()
        self.assertEqual(message.content, "Hello")
        self.assertIsNone(message.deleted_at)

    def test_cross_conversation_reply_is_rejected(self):
        other_workspace = Workspace.objects.create(
            name="Another Message Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.alice,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.bob,
            role=WorkspaceMembership.Role.MEMBER,
        )

        other_conversation = get_or_create_direct_chat(
            workspace_slug=other_workspace.slug,
            recipient=self.bob,
            actor=self.alice,
        )
        foreign_message = ChatMessage.objects.create(
            conversation=other_conversation,
            sender=self.alice,
            content="Foreign message",
        )

        with self.assertRaises(ValidationError):
            self.create_message(
                content="Invalid reply",
                reply_to=foreign_message.pk,
            )

    def test_soft_delete_preserves_reply(self):
        parent = self.create_message()
        reply = self.create_message(
            actor=self.bob,
            content="Reply",
            reply_to=parent.pk,
        )

        delete_chat_message(
            workspace_slug=self.workspace.slug,
            message_id=parent.pk,
            actor=self.alice,
        )

        parent.refresh_from_db()
        reply.refresh_from_db()

        self.assertEqual(parent.content, "")
        self.assertIsNotNone(parent.deleted_at)
        self.assertEqual(reply.reply_to_id, parent.pk)

        with self.assertRaises(ValidationError):
            update_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=parent.pk,
                actor=self.alice,
                content="Restore",
            )

    def test_rejects_invalid_message_content(self):
        for content in ("", "   ", None, 123, "x" * 5001):
            with self.subTest(content=content):
                with self.assertRaises(ValidationError):
                    self.create_message(content=content)

        self.assertFalse(ChatMessage.objects.exists())

    def test_messages_are_returned_newest_first(self):
        first = self.create_message(content="First")
        second = self.create_message(content="Second")

        messages = list(get_chat_messages(
            workspace_slug=self.workspace.slug,
            conversation_id=self.conversation.pk,
            actor=self.bob,
        ))

        self.assertEqual(
            [message.pk for message in messages],
            [second.pk, first.pk],
        )
