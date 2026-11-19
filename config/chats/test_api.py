
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from chats.models import ChatMessage
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="chat-api-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="chat-api-member@example.com",
            password="Strong-password-2026!",
        )
        self.admin = User.objects.create_user(
            email="chat-api-admin@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Chat API Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
            (self.admin, WorkspaceMembership.Role.ADMIN),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Chat API Project",
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

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

        self.direct_url = reverse(
            "workspaces_api_v1:chats_api_v1:direct-list-create",
            kwargs={"slug": self.workspace.slug},
        )
        self.project_url = reverse(
            "workspaces_api_v1:project-chat",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
            },
        )

    def create_direct(self):
        response = self.client.post(
            self.direct_url,
            {"recipient_id": self.member.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.data["id"]

    def messages_url(self, conversation_id):
        return reverse(
            "workspaces_api_v1:chats_api_v1:message-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "conversation_id": conversation_id,
            },
        )

    def message_url(self, conversation_id, message_id):
        return reverse(
            "workspaces_api_v1:chats_api_v1:message-detail",
            kwargs={
                "slug": self.workspace.slug,
                "conversation_id": conversation_id,
                "message_id": message_id,
            },
        )

    def test_project_chat_access_and_reuse(self):
        first = self.client.get(self.project_url)
        second = self.client.get(self.project_url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])

        self.client.force_authenticate(user=self.admin)
        self.assertEqual(
            self.client.get(self.project_url).status_code,
            200,
        )

    def test_direct_creation_and_listing(self):
        conversation_id = self.create_direct()

        response = self.client.get(self.direct_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], conversation_id)

        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.direct_url)
        self.assertEqual(len(response.data), 1)

    def test_admin_cannot_access_others_direct(self):
        conversation_id = self.create_direct()
        self.client.force_authenticate(user=self.admin)

        self.assertEqual(
            self.client.get(
                self.messages_url(conversation_id)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                self.messages_url(conversation_id),
                {"content": "Private message"},
                format="json",
            ).status_code,
            404,
        )

    def test_send_reply_edit_delete(self):
        conversation_id = self.create_direct()
        url = self.messages_url(conversation_id)

        first = self.client.post(
            url, {"content": "Hello"}, format="json"
        )
        self.assertEqual(first.status_code, 201)

        self.client.force_authenticate(user=self.member)
        reply = self.client.post(
            url,
            {
                "content": "Hi",
                "reply_to": first.data["id"],
            },
            format="json",
        )
        self.assertEqual(reply.status_code, 201)

        detail_url = self.message_url(
            conversation_id, reply.data["id"]
        )
        updated = self.client.patch(
            detail_url,
            {"content": "Updated"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["content"], "Updated")

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204)

        message = ChatMessage.objects.get(
            pk=reply.data["id"]
        )
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.content, "")

    def test_message_list_is_paginated(self):
        conversation_id = self.create_direct()
        url = self.messages_url(conversation_id)

        for index in range(3):
            response = self.client.post(
                url,
                {"content": f"Message {index}"},
                format="json",
            )
            self.assertEqual(response.status_code, 201)

        response = self.client.get(
            url, {"page_size": 2}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_unauthenticated_requests_are_rejected(self):
        self.client.force_authenticate(user=None)

        self.assertIn(
            self.client.get(self.direct_url).status_code,
            (401, 403),
        )
        self.assertIn(
            self.client.get(self.project_url).status_code,
            (401, 403),
        )

    def test_invalid_message_is_rejected(self):
        conversation_id = self.create_direct()
        response = self.client.post(
            self.messages_url(conversation_id),
            {"content": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_message_detail_rejects_wrong_conversation(self):
        first_id = self.create_direct()

        first_response = self.client.post(
            self.messages_url(first_id),
            {"content": "Private message"},
            format="json",
        )
        self.assertEqual(first_response.status_code, 201)

        other_workspace = Workspace.objects.create(
            name="Another Chat API Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        other_direct_url = reverse(
            "workspaces_api_v1:chats_api_v1:direct-list-create",
            kwargs={"slug": other_workspace.slug},
        )
        other_response = self.client.post(
            other_direct_url,
            {"recipient_id": self.member.pk},
            format="json",
        )
        self.assertEqual(other_response.status_code, 200)

        wrong_detail_url = self.message_url(
            other_response.data["id"],
            first_response.data["id"],
        )

        self.assertEqual(
            self.client.patch(
                wrong_detail_url,
                {"content": "Unauthorized edit"},
                format="json",
            ).status_code,
            404,
        )

        self.assertEqual(
            self.client.delete(wrong_detail_url).status_code,
            404,
        )

        message = ChatMessage.objects.get(
            pk=first_response.data["id"],
        )
        self.assertEqual(message.content, "Private message")
        self.assertIsNone(message.deleted_at)

    def test_removed_workspace_member_cannot_read_direct(self):
        conversation_id = self.create_direct()

        response = self.client.post(
            self.messages_url(conversation_id),
            {"content": "Before removal"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).delete()

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        self.client.force_authenticate(user=self.member)

        self.assertEqual(
            self.client.get(
                self.messages_url(conversation_id)
            ).status_code,
            404,
        )

        self.assertEqual(
            self.client.post(
                self.messages_url(conversation_id),
                {"content": "After removal"},
                format="json",
            ).status_code,
            404,
        )
