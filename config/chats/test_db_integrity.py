from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from chats.models import (
    ChatMessage,
    Conversation,
    ConversationParticipant,
)
from workspaces.models import Workspace, WorkspaceMembership
from projects.models import Project, ProjectMembership


User = get_user_model()


class ChatDatabaseIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="chat-integrity@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Chat Integrity Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.first = Conversation.objects.create(
            workspace=self.workspace,
            type=Conversation.Type.DIRECT,
            direct_user_low=self.user,
            direct_user_high=User.objects.create_user(
                email="chat-integrity-second@example.com",
                password="Strong-password-2026!",
            ),
        )

        self.third_user = User.objects.create_user(
            email="chat-integrity-third@example.com",
            password="Strong-password-2026!",
        )

        self.second = Conversation.objects.create(
            workspace=self.workspace,
            type=Conversation.Type.DIRECT,
            direct_user_low=self.user,
            direct_user_high=self.third_user,
        )

        self.parent = ChatMessage.objects.create(
            conversation=self.first,
            sender=self.user,
            content="Parent message",
        )

    def test_rejects_cross_conversation_reply(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatMessage.objects.create(
                    conversation=self.second,
                    sender=self.user,
                    content="Invalid reply",
                    reply_to=self.parent,
                )

    def test_accepts_same_conversation_reply(self):
        reply = ChatMessage.objects.create(
            conversation=self.first,
            sender=self.user,
            content="Valid reply",
            reply_to=self.parent,
        )

        self.assertEqual(
            reply.reply_to_id,
            self.parent.pk,
        )

    def test_rejects_cross_conversation_last_read(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConversationParticipant.objects.create(
                    conversation=self.second,
                    user=self.user,
                    last_read_message=self.parent,
                )

    def test_accepts_same_conversation_last_read(self):
        participant = ConversationParticipant.objects.create(
            conversation=self.first,
            user=self.user,
            last_read_message=self.parent,
        )

        self.assertEqual(
            participant.last_read_message_id,
            self.parent.pk,
        )

    def test_rejects_project_chat_in_wrong_workspace(self):
        other_workspace = Workspace.objects.create(
            name="Other Chat Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        project = Project.objects.create(
            workspace=other_workspace,
            name="Other Workspace Project",
            created_by=self.user,
        )

        ProjectMembership.objects.create(
            project=project,
            user=self.user,
            role=ProjectMembership.Role.MANAGER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(
                    workspace=self.workspace,
                    type=Conversation.Type.PROJECT,
                    project=project,
                )

    def test_accepts_project_chat_in_correct_workspace(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Valid Chat Project",
            created_by=self.user,
        )

        ProjectMembership.objects.create(
            project=project,
            user=self.user,
            role=ProjectMembership.Role.MANAGER,
        )

        conversation = Conversation.objects.create(
            workspace=self.workspace,
            type=Conversation.Type.PROJECT,
            project=project,
        )

        self.assertEqual(
            conversation.workspace_id,
            project.workspace_id,
        )

    def test_rejects_conversation_workspace_transfer(self):
        other_workspace = Workspace.objects.create(
            name="Transfer Target Workspace",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.filter(
                    pk=self.first.pk,
                ).update(
                    workspace=other_workspace,
                )

    def test_rejects_message_conversation_transfer(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatMessage.objects.filter(
                    pk=self.parent.pk,
                ).update(
                    conversation=self.second,
                )

    def test_rejects_participant_conversation_transfer(self):
        participant = ConversationParticipant.objects.create(
            conversation=self.first,
            user=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConversationParticipant.objects.filter(
                    pk=participant.pk,
                ).update(
                    conversation=self.second,
                )

    def test_rejects_participant_user_transfer(self):
        participant = ConversationParticipant.objects.create(
            conversation=self.first,
            user=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConversationParticipant.objects.filter(
                    pk=participant.pk,
                ).update(
                    user=self.third_user,
                )

    def test_rejects_conversation_direct_user_transfer(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.filter(
                    pk=self.first.pk,
                ).update(
                    direct_user_high=self.third_user,
                )
