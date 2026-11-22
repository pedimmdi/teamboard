
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from chats.services import (
    create_chat_message,
    update_chat_message,
    delete_chat_message,
    get_or_create_direct_chat,
)
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatServiceEventTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="event-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="event-member@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Chat Service Events Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.conversation = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )

    @patch("chats.events.publish_chat_event")
    def test_create_schedules_event(self, publish):
        with self.captureOnCommitCallbacks(execute=True):
            message = create_chat_message(
                workspace_slug=self.workspace.slug,
                conversation_id=self.conversation.pk,
                actor=self.owner,
                content="Hello from REST",
            )

            publish.assert_not_called()

        publish.assert_called_once_with(
            conversation_id=self.conversation.pk,
            event_type="message.created",
            message_id=message.pk,
        )

    @patch("chats.events.publish_chat_event")
    def test_update_schedules_event(self, publish):
        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.conversation.pk,
            actor=self.owner,
            content="Original message",
        )

        with self.captureOnCommitCallbacks(execute=True):
            update_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.owner,
                content="Updated message",
            )

            publish.assert_not_called()

        publish.assert_called_once_with(
            conversation_id=self.conversation.pk,
            event_type="message.updated",
            message_id=message.pk,
        )

    @patch("chats.events.publish_chat_event")
    def test_delete_schedules_event_once(self, publish):
        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.conversation.pk,
            actor=self.owner,
            content="Delete this message",
        )

        with self.captureOnCommitCallbacks(execute=True):
            delete_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.owner,
            )

            publish.assert_not_called()

        publish.assert_called_once_with(
            conversation_id=self.conversation.pk,
            event_type="message.deleted",
            message_id=message.pk,
        )

        publish.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            delete_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.owner,
            )

        publish.assert_not_called()
