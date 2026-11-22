from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from chats.models import ChatMessage, ConversationParticipant
from chats.services import get_or_create_direct_chat, get_or_create_project_chat
from chats.unread import get_unread_chats, mark_chat_read
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()


class ChatUnreadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.admin, cls.alice, cls.bob, cls.outsider = [User.objects.create_user(email=f"unread-{name}@example.com") for name in ("owner", "admin", "alice", "bob", "outsider")]
        cls.workspace = Workspace.objects.create(name="Unread tests")
        for user, role in ((cls.owner, "owner"), (cls.admin, "admin"), (cls.alice, "member"), (cls.bob, "member")):
            WorkspaceMembership.objects.create(workspace=cls.workspace, user=user, role=role)
        cls.project = Project.objects.create(workspace=cls.workspace, name="Private", created_by=cls.owner)
        ProjectMembership.objects.create(project=cls.project, user=cls.owner, role="manager")
        cls.alice_membership = ProjectMembership.objects.create(project=cls.project, user=cls.alice, role="member")
        cls.group = get_or_create_project_chat(workspace_slug=cls.workspace.slug, project_id=cls.project.pk, actor=cls.owner)
        cls.direct = get_or_create_direct_chat(workspace_slug=cls.workspace.slug, actor=cls.alice, recipient=cls.bob)
        cls.other_direct = get_or_create_direct_chat(workspace_slug=cls.workspace.slug, actor=cls.owner, recipient=cls.bob)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.alice)
        self.base = f"/api/v1/workspaces/{self.workspace.slug}/chats/"

    def message(self, conversation=None, sender=None, **kwargs):
        return ChatMessage.objects.create(conversation=conversation or self.direct, sender=sender or self.bob, content="Message", **kwargs)

    def summary(self, user=None):
        return get_unread_chats(workspace_slug=self.workspace.slug, actor=user or self.alice)

    def read(self, message):
        return self.client.post(f"{self.base}{message.conversation_id}/read/", {"message_id": str(message.pk)}, format="json")

    def test_totals_include_only_received_non_deleted_accessible_messages(self):
        self.message()
        self.message(conversation=self.group, sender=self.owner)
        self.message(conversation=self.other_direct)
        self.message(sender=self.alice)
        deleted = self.message()
        deleted.deleted_at = deleted.created_at
        deleted.save(update_fields=["deleted_at"])
        response = self.client.get(self.base + "unread/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 2)
        self.assertEqual({row["id"] for row in response.data["conversations"]}, {str(self.direct.pk), str(self.group.pk)})
        direct = next(row for row in response.data["conversations"] if row["id"] == str(self.direct.pk))
        self.assertEqual(direct["recipient_id"], self.bob.pk)

    def test_membership_revocation_and_privileged_project_access(self):
        self.message(conversation=self.group, sender=self.owner)
        self.assertEqual(self.summary(self.admin)["unread_count"], 1)
        self.assertEqual(self.summary(self.bob)["unread_count"], 0)
        self.alice_membership.delete()
        self.assertEqual(self.summary()["unread_count"], 0)
        response = self.client.post(f"{self.base}{self.group.pk}/read/", {"message_id": str(self.message(conversation=self.group).pk)}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_read_cursor_is_monotonic_and_does_not_acknowledge_newer_messages(self):
        first, second, third = self.message(), self.message(), self.message()
        self.assertEqual(self.read(second).status_code, 204)
        self.assertEqual(self.summary()["unread_count"], 1)
        self.assertEqual(self.read(first).status_code, 204)
        self.assertEqual(self.summary()["unread_count"], 1)
        self.assertEqual(self.read(third).status_code, 204)
        self.assertEqual(self.summary()["unread_count"], 0)

    def test_timestamp_ties_use_uuid_order_and_survive_deleted_cursor(self):
        first = self.message(id=UUID(int=1))
        second = self.message(id=UUID(int=2))
        ChatMessage.objects.filter(pk=second.pk).update(created_at=first.created_at)
        self.assertEqual(self.read(first).status_code, 204)
        self.assertEqual(self.summary()["unread_count"], 1)
        first.delete()
        self.assertEqual(self.summary()["unread_count"], 1)

    def test_deleted_messages_reduce_counts_and_own_messages_do_not_count(self):
        message = self.message()
        self.assertEqual(self.summary()["unread_count"], 1)
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.delete(f"{self.base}{self.direct.pk}/messages/{message.pk}/").status_code, 204)
        self.assertEqual(self.summary()["unread_count"], 0)

    def test_read_rejects_cross_conversation_targets_invalid_uuid_and_missing_id(self):
        foreign = self.message(conversation=self.other_direct)
        response = self.client.post(f"{self.base}{self.direct.pk}/read/", {"message_id": str(foreign.pk)}, format="json")
        self.assertEqual(response.status_code, 404)
        for data in ({}, {"message_id": "invalid"}):
            self.assertEqual(self.client.post(f"{self.base}{self.direct.pk}/read/", data, format="json").status_code, 400)

    def test_outsiders_other_workspaces_and_signed_out_users_cannot_read_counts(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.base + "unread/").status_code, 404)
        self.client.force_authenticate(self.alice)
        WorkspaceMembership.objects.filter(workspace=self.workspace, user=self.alice).delete()
        self.assertEqual(self.client.get(self.base + "unread/").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.base + "unread/").status_code, 401)

    def test_reply_reference_is_uuid_and_older_message_can_be_retrieved_securely(self):
        parent = self.message()
        reply = self.message(reply_to=parent)
        response = self.client.get(f"{self.base}{self.direct.pk}/messages/")
        self.assertEqual(next(row for row in response.data["results"] if row["id"] == str(reply.pk))["reply_to"], str(parent.pk))
        self.assertEqual(self.client.get(f"{self.base}{self.direct.pk}/messages/{parent.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"{self.base}{self.group.pk}/messages/{parent.pk}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"{self.base}{self.direct.pk}/messages/{parent.pk}/").status_code, 404)

    def test_summary_query_count_does_not_grow_with_message_count(self):
        self.message()
        with CaptureQueriesContext(connection) as before:
            self.summary()
        ChatMessage.objects.bulk_create([ChatMessage(conversation=self.direct, sender=self.bob, content="Bulk") for _ in range(100)])
        with CaptureQueriesContext(connection) as after:
            summary = self.summary()
        self.assertEqual(summary["unread_count"], 101)
        self.assertEqual(len(before), len(after))
        self.assertLessEqual(len(after), 5)


class ChatReadTransactionTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="cursor-alice@example.com")
        self.bob = User.objects.create_user(email="cursor-bob@example.com")
        self.workspace = Workspace.objects.create(name="Read cursor")
        for user, role in ((self.alice, "owner"), (self.bob, "member")):
            WorkspaceMembership.objects.create(workspace=self.workspace, user=user, role=role)
        self.conversation = get_or_create_direct_chat(workspace_slug=self.workspace.slug, actor=self.alice, recipient=self.bob)
        self.first = ChatMessage.objects.create(conversation=self.conversation, sender=self.bob, content="First")
        self.last = ChatMessage.objects.create(conversation=self.conversation, sender=self.bob, content="Last")

    def test_concurrent_acknowledgements_never_regress(self):
        start = Barrier(2)
        def acknowledge(message):
            try:
                start.wait(timeout=10)
                mark_chat_read(workspace_slug=self.workspace.slug, conversation_id=self.conversation.pk, actor=self.alice, message_id=message.pk)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(acknowledge, (self.first, self.last)))
        self.assertEqual(ConversationParticipant.objects.get(conversation=self.conversation, user=self.alice).last_read_message_id, self.last.pk)

    def test_migration_preserves_existing_read_pointer(self):
        previous = [("chats", "0005_chat_relationship_integrity")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(previous)
            Participant = executor.loader.project_state(previous).apps.get_model("chats", "ConversationParticipant")
            Participant.objects.filter(conversation_id=self.conversation.pk, user_id=self.alice.pk).update(last_read_message_id=self.first.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
        participant = ConversationParticipant.objects.get(conversation=self.conversation, user=self.alice)
        self.assertEqual(participant.last_read_at, self.first.created_at)
        self.assertEqual(participant.last_read_key, self.first.pk)
        self.assertEqual(get_unread_chats(workspace_slug=self.workspace.slug, actor=self.alice)["unread_count"], 1)
