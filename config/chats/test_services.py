
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from chats.access import get_conversation_or_404
from chats.models import Conversation, ConversationParticipant
from chats.services import (
    get_or_create_direct_chat,
    get_or_create_project_chat,
)
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="chat-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="chat-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="chat-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Chats Workspace",
        )
        self.other_workspace = Workspace.objects.create(
            name="Other Chats Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        WorkspaceMembership.objects.create(
            workspace=self.other_workspace,
            user=self.outsider,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Chats Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

    def test_project_chat_is_reused(self):
        first = get_or_create_project_chat(
            workspace_slug=self.workspace.slug,
            project_id=self.project.pk,
            actor=self.owner,
        )
        second = get_or_create_project_chat(
            workspace_slug=self.workspace.slug,
            project_id=self.project.pk,
            actor=self.member,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.project_id, self.project.pk)
        self.assertEqual(
            Conversation.objects.filter(
                project=self.project,
            ).count(),
            1,
        )

    def test_project_chat_rejects_non_member(self):
        with self.assertRaises(Http404):
            get_or_create_project_chat(
                workspace_slug=self.workspace.slug,
                project_id=self.project.pk,
                actor=self.outsider,
            )

    def test_direct_is_reused_in_reverse_order(self):
        first = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )
        second = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.owner,
            actor=self.member,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Conversation.objects.filter(
                type=Conversation.Type.DIRECT,
            ).count(),
            1,
        )
        self.assertEqual(
            set(first.participants.values_list(
                "user_id", flat=True
            )),
            {self.owner.pk, self.member.pk},
        )

    def test_direct_rejects_self_and_outsider(self):
        for recipient in (self.owner, self.outsider):
            with self.subTest(recipient=recipient.pk):
                with self.assertRaises(PermissionDenied):
                    get_or_create_direct_chat(
                        workspace_slug=self.workspace.slug,
                        recipient=recipient,
                        actor=self.owner,
                    )

        self.assertFalse(Conversation.objects.exists())

    def test_direct_is_private(self):
        direct = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )

        result = get_conversation_or_404(
            workspace_slug=self.workspace.slug,
            conversation_id=direct.pk,
            actor=self.member,
        )
        self.assertEqual(result.pk, direct.pk)

        with self.assertRaises(Http404):
            get_conversation_or_404(
                workspace_slug=self.other_workspace.slug,
                conversation_id=direct.pk,
                actor=self.outsider,
            )

    def test_direct_pair_has_database_uniqueness(self):
        first = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(
                    workspace=self.workspace,
                    type=Conversation.Type.DIRECT,
                    direct_user_low_id=first.direct_user_low_id,
                    direct_user_high_id=first.direct_user_high_id,
                )

    def test_direct_rejects_reversed_pair_in_database(self):
        low_id, high_id = sorted(
            (self.owner.pk, self.member.pk)
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(
                    workspace=self.workspace,
                    type=Conversation.Type.DIRECT,
                    direct_user_low_id=high_id,
                    direct_user_high_id=low_id,
                )

    def test_direct_access_rechecks_workspace_membership(self):
        direct = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )
        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        with self.assertRaises(Http404):
            get_conversation_or_404(
                workspace_slug=self.workspace.slug,
                conversation_id=direct.pk,
                actor=self.member,
            )
