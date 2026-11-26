from unittest.mock import sentinel
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification
from projects.models import Project, ProjectMembership
from workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from tasks.models import Task


User = get_user_model()


class NotificationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="notification-user@example.com",
            password="TestPassword123!",
        )
        cls.other_user = User.objects.create_user(
            email="notification-other@example.com",
            password="TestPassword123!",
        )
        cls.actor = User.objects.create_user(
            email="notification-actor@example.com",
            password="TestPassword123!",
        )

        cls.workspace = Workspace.objects.create(
            name="Notification Test Workspace",
        )

        cls.workspace_membership = (
            WorkspaceMembership.objects.create(
                workspace=cls.workspace,
                user=cls.user,
                role=WorkspaceMembership.Role.MEMBER,
            )
        )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="Notification Test Project",
            created_by=cls.user,
        )

        cls.project_membership = (
            ProjectMembership.objects.create(
                project=cls.project,
                user=cls.user,
                role=ProjectMembership.Role.MEMBER,
            )
        )

        # Keep an independent, workspace-eligible project manager.
        # This membership must remain intact when tests remove
        # the regular user's project/workspace membership.
        cls.manager = User.objects.create_user(
            email="notification-manager@example.com",
            password="TestPassword123!",
        )

        cls.manager_workspace_membership = (
            WorkspaceMembership.objects.create(
                workspace=cls.workspace,
                user=cls.manager,
                role=WorkspaceMembership.Role.ADMIN,
            )
        )

        cls.manager_project_membership = (
            ProjectMembership.objects.create(
                project=cls.project,
                user=cls.manager,
                role=ProjectMembership.Role.MANAGER,
            )
        )

        cls.task = Task.objects.create(
            project=cls.project,
            title="Default Notification Task",
            created_by=cls.user,
            assignee=cls.user,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.list_url = reverse("notification-list")
        self.count_url = reverse("notification-unread-count")

    def make_notification(
        self,
        *,
        recipient=None,
        workspace=sentinel.default_workspace,
        project=sentinel.default_project,
        task=sentinel.default_task,
        read=False,
        event_type=Notification.EventType.TASK_ASSIGNED,
    ):
        if workspace is sentinel.default_workspace:
            workspace = self.workspace

        if project is sentinel.default_project:
            if event_type in (
                Notification.EventType.WORKSPACE_INVITED,
                Notification.EventType.WORKSPACE_ROLE_CHANGED,
            ):
                project = None
            else:
                project = self.project

        if task is sentinel.default_task:
            if event_type in (
                Notification.EventType.TASK_ASSIGNED,
                Notification.EventType.TASK_UPDATED,
                Notification.EventType.COMMENT_MENTIONED,
                Notification.EventType.COMMENT_REPLIED,
            ):
                task = self.task
            else:
                task = None

        return Notification.objects.create(
            recipient=recipient or self.user,
            actor=self.actor,
            event_type=event_type,
            workspace=workspace,
            project=project,
            task=task,
            payload={"message": "Test notification"},
            deduplication_key=f"api-test:{uuid4()}",
            read_at=timezone.now() if read else None,
        )

    def test_list_fetches_related_display_fields_in_the_page_query(self):
        readings = [self.make_notification() for _ in range(8)]
        with self.assertNumQueries(2) as queries:
            response = self.client.get(self.list_url, {"page_size": 5})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 8)
        self.assertEqual(len(response.data["results"]), 5)
        latest = response.data["results"][0]
        self.assertEqual(latest["id"], str(readings[-1].pk))
        self.assertEqual(latest["task_title"], self.task.title)
        self.assertEqual(latest["workspace_name"], self.workspace.name)
        self.assertEqual(latest["project_name"], self.project.name)
        self.assertNotIn('"tasks_task"."description"', queries.captured_queries[-1]["sql"])

    def test_list_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unread_count_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.count_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_list_returns_only_own_notifications(self):
        own = self.make_notification()
        self.make_notification(recipient=self.other_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(own.pk),
        )

    def test_list_does_not_expose_internal_fields(self):
        self.make_notification()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data["results"][0]

        self.assertNotIn("recipient", data)
        self.assertNotIn("deduplication_key", data)
        self.assertIn("is_read", data)
        self.assertIn("read_at", data)

    def test_list_exposes_destination_details_for_accessible_notifications(self):
        self.make_notification()

        data = self.client.get(self.list_url).data["results"][0]

        self.assertEqual(data["workspace_slug"], self.workspace.slug)
        self.assertEqual(data["workspace_name"], self.workspace.name)
        self.assertEqual(data["project_name"], self.project.name)
        self.assertEqual(data["task_title"], self.task.title)

    def test_list_orders_newest_first(self):
        older = self.make_notification()
        newer = self.make_notification()

        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(newer.pk), str(older.pk)],
        )

    def test_filter_unread_notifications(self):
        unread = self.make_notification()
        self.make_notification(read=True)

        response = self.client.get(
            self.list_url,
            {"read": "false"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(unread.pk),
        )

    def test_filter_read_notifications(self):
        self.make_notification()
        read = self.make_notification(read=True)

        response = self.client.get(
            self.list_url,
            {"read": "true"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(read.pk),
        )

    def test_invalid_read_filter_returns_400(self):
        for value in ("invalid", "1", "yes", ""):
            with self.subTest(value=value):
                response = self.client.get(
                    self.list_url,
                    {"read": value},
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

    def test_unread_count_only_counts_own_unread(self):
        self.make_notification()
        self.make_notification()
        self.make_notification(read=True)
        self.make_notification(recipient=self.other_user)

        response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {"unread_count": 2},
        )

    def test_pagination_default_page_size(self):
        for _ in range(25):
            self.make_notification()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_pagination_custom_page_size(self):
        for _ in range(7):
            self.make_notification()

        response = self.client.get(
            self.list_url,
            {"page_size": 3},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 7)
        self.assertEqual(len(response.data["results"]), 3)

    def test_pagination_max_page_size(self):
        for _ in range(105):
            self.make_notification()

        response = self.client.get(
            self.list_url,
            {"page_size": 200},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 105)
        self.assertEqual(len(response.data["results"]), 100)

    def test_workspace_notification_visible_to_member(self):
        notification = self.make_notification(
            workspace=self.workspace,
            project=None,
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(notification.pk),
        )

    def test_workspace_notification_hidden_after_membership_removed(self):
        self.make_notification(
            workspace=self.workspace,
            project=None,
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )

        self.workspace_membership.delete()

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(count_response.data["unread_count"], 0)

    def test_project_notification_visible_to_project_member(self):
        notification = self.make_notification(
            workspace=self.workspace,
            project=self.project,
            event_type=Notification.EventType.PROJECT_MEMBER_ADDED,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(notification.pk),
        )

    def test_project_notification_hidden_after_project_membership_removed(self):
        self.make_notification(
            workspace=self.workspace,
            project=self.project,
        )

        self.project_membership.delete()

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(count_response.data["unread_count"], 0)

    def test_project_notification_hidden_after_workspace_membership_removed(self):
        self.make_notification(
            workspace=self.workspace,
            project=self.project,
        )

        self.workspace_membership.delete()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_workspace_admin_can_view_project_notification(self):
        self.make_notification(
            workspace=self.workspace,
            project=self.project,
        )

        self.project_membership.delete()

        self.workspace_membership.role = (
            WorkspaceMembership.Role.ADMIN
        )
        self.workspace_membership.save(update_fields=["role"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_workspace_owner_can_view_project_notification(self):
        self.make_notification(
            workspace=self.workspace,
            project=self.project,
        )

        self.project_membership.delete()

        self.workspace_membership.role = (
            WorkspaceMembership.Role.OWNER
        )
        self.workspace_membership.save(update_fields=["role"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_task_event_without_task_is_hidden(self):
        notification = self.make_notification(
            event_type=Notification.EventType.TASK_ASSIGNED,
            task=None,
        )

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            count_response.data["unread_count"],
            0,
        )

        self.assertTrue(
            Notification.objects.filter(pk=notification.pk).exists()
        )

    def test_project_event_with_task_is_hidden(self):
        self.make_notification(
            event_type=Notification.EventType.PROJECT_MEMBER_ADDED,
            task=self.task,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_project_event_without_project_is_hidden(self):
        self.make_notification(
            event_type=Notification.EventType.PROJECT_ROLE_CHANGED,
            project=None,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_workspace_event_with_project_is_hidden(self):
        self.make_notification(
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
            project=self.project,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_invalid_scope_cannot_be_marked_read(self):
        notification = self.make_notification(
            event_type=Notification.EventType.TASK_UPDATED,
            task=None,
        )

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_mark_all_read_skips_invalid_scope(self):
        valid_notification = self.make_notification()

        invalid_notification = self.make_notification(
            event_type=Notification.EventType.TASK_ASSIGNED,
            task=None,
        )

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data,
            {"updated_count": 1},
        )

        valid_notification.refresh_from_db()
        invalid_notification.refresh_from_db()

        self.assertIsNotNone(valid_notification.read_at)
        self.assertIsNone(invalid_notification.read_at)

    def test_post_is_not_allowed_on_list(self):
        response = self.client.post(
            self.list_url,
            {"event_type": "task_assigned"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_notification_without_scope_is_hidden(self):
        self.make_notification(
            workspace=None,
            project=None,
        )

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(count_response.data["unread_count"], 0)

    def test_workspace_invitation_visible_to_non_member(self):
        invitation = WorkspaceInvitation.objects.create(
            workspace=self.workspace,
            email=self.user.email,
            invited_by=self.actor,
            token_hash=uuid4().hex,
            expires_at=timezone.now() + timedelta(days=7),
        )

        notification = self.make_notification(
            event_type=Notification.EventType.WORKSPACE_INVITED,
        )
        notification.payload = {
            "invitation_id": str(invitation.pk),
        }
        notification.save(update_fields=["payload"])

        self.workspace_membership.delete()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(notification.pk),
        )

    def test_accept_invitation_from_inbox_requires_recipient_and_verified_email(self):
        self.workspace_membership.delete()
        invitation = WorkspaceInvitation.objects.create(
            workspace=self.workspace,
            email=self.user.email,
            invited_by=self.actor,
            token_hash=uuid4().hex,
            expires_at=timezone.now() + timedelta(days=7),
        )
        notification = self.make_notification(
            event_type=Notification.EventType.WORKSPACE_INVITED,
        )
        notification.payload = {"invitation_id": str(invitation.pk)}
        notification.save(update_fields=["payload"])
        url = reverse("notification-accept-invitation", args=[notification.pk])

        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_authenticate(user=self.user)
        self.user.is_email_verified = False
        self.assertEqual(self.client.post(url).status_code, 400)
        self.user.is_email_verified = True
        self.assertEqual(self.client.post(url).status_code, 204)
        self.assertEqual(self.client.post(url).status_code, 404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, WorkspaceInvitation.Status.ACCEPTED)
        self.assertTrue(WorkspaceMembership.objects.filter(
            user=self.user, workspace=self.workspace, role=WorkspaceMembership.Role.MEMBER,
        ).exists())

    def test_notification_hidden_after_workspace_deleted(self):
        self.make_notification(
            workspace=self.workspace,
            project=None,
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )

        self.project.delete()
        self.workspace.delete()

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(count_response.data["unread_count"], 0)

    def test_notification_with_matching_task_is_visible(self):
        task = Task.objects.create(
            project=self.project,
            title="Matching notification task",
            created_by=self.user,
        )

        notification = self.make_notification()

        notification.task = task
        notification.save(update_fields=["task"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(notification.pk),
        )

    def test_notification_with_mismatched_task_is_hidden(self):
        other_project = Project.objects.create(
            workspace=self.workspace,
            name="Other Notification Project",
            created_by=self.user,
        )

        ProjectMembership.objects.create(
            project=other_project,
            user=self.manager,
            role=ProjectMembership.Role.MANAGER,
        )

        other_task = Task.objects.create(
            project=other_project,
            title="Task from another project",
            created_by=self.manager,
        )

        notification = self.make_notification(
            task=other_task,
        )

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(count_response.data["unread_count"], 0)

    def test_notification_payload_is_not_exposed(self):
        notification = self.make_notification()

        notification.payload = {
            "message": "Internal information",
            "invitation_token": "private-token",
            "secret": "confidential-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["count"], 1)

        data = response.data["results"][0]

        self.assertEqual(data["payload"], {})
        self.assertNotIn(
            "private-token",
            str(response.data),
        )
        self.assertNotIn(
            "confidential-value",
            str(response.data),
        )

    def test_notification_serializer_is_read_only(self):
        notification = self.make_notification()

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = response.data["results"][0]

        self.assertEqual(
            data["id"],
            str(notification.pk),
        )
        self.assertIn("event_type", data)
        self.assertIn("created_at", data)
        self.assertIn("is_read", data)
        self.assertEqual(data["payload"], {})

    def test_mark_read_requires_authentication(self):
        notification = self.make_notification()
        self.client.force_authenticate(user=None)

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_mark_read_updates_unread_notification(self):
        notification = self.make_notification()

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notification.refresh_from_db()

        self.assertIsNotNone(notification.read_at)
        self.assertTrue(response.data["is_read"])
        self.assertIsNotNone(response.data["read_at"])
        self.assertEqual(response.data["payload"], {})

    def test_mark_read_is_idempotent(self):
        notification = self.make_notification()

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        first_response = self.client.post(url)

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        notification.refresh_from_db()
        original_read_at = notification.read_at

        second_response = self.client.post(url)

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )

        notification.refresh_from_db()

        self.assertEqual(
            notification.read_at,
            original_read_at,
        )

    def test_mark_read_cannot_modify_another_users_notification(self):
        notification = self.make_notification(
            recipient=self.other_user,
        )

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_mark_read_cannot_modify_inaccessible_notification(self):
        notification = self.make_notification()

        self.project_membership.delete()

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_mark_read_returns_404_for_missing_notification(self):
        url = reverse(
            "notification-mark-read",
            kwargs={"pk": uuid4()},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_mark_all_read_requires_authentication(self):
        self.make_notification()
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_mark_all_read_updates_only_unread_notifications(self):
        first = self.make_notification()
        second = self.make_notification()
        already_read = self.make_notification(read=True)

        original_read_at = already_read.read_at

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data,
            {"updated_count": 2},
        )

        first.refresh_from_db()
        second.refresh_from_db()
        already_read.refresh_from_db()

        self.assertIsNotNone(first.read_at)
        self.assertIsNotNone(second.read_at)
        self.assertEqual(
            already_read.read_at,
            original_read_at,
        )

        count_response = self.client.get(self.count_url)

        self.assertEqual(
            count_response.data,
            {"unread_count": 0},
        )

    def test_mark_all_read_is_idempotent(self):
        self.make_notification()
        self.make_notification()

        url = reverse("notification-mark-all-read")

        first_response = self.client.post(url)
        second_response = self.client.post(url)

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            first_response.data,
            {"updated_count": 2},
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            second_response.data,
            {"updated_count": 0},
        )

    def test_mark_all_read_does_not_modify_other_users_notifications(self):
        own = self.make_notification()
        other = self.make_notification(
            recipient=self.other_user,
        )

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data,
            {"updated_count": 1},
        )

        own.refresh_from_db()
        other.refresh_from_db()

        self.assertIsNotNone(own.read_at)
        self.assertIsNone(other.read_at)

    def test_mark_all_read_skips_inaccessible_notifications(self):
        accessible = self.make_notification(
            workspace=self.workspace,
            project=None,
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )

        inaccessible = self.make_notification()

        self.project_membership.delete()

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data,
            {"updated_count": 1},
        )

        accessible.refresh_from_db()
        inaccessible.refresh_from_db()

        self.assertIsNotNone(accessible.read_at)
        self.assertIsNone(inaccessible.read_at)

    def test_mark_all_read_with_no_notifications(self):
        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data,
            {"updated_count": 0},
        )

    def test_removed_project_member_cannot_read_old_task_notification(self):
        notification = self.make_notification(
            event_type=Notification.EventType.COMMENT_MENTIONED,
        )

        self.project_membership.delete()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

        read_url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        read_response = self.client.post(read_url)

        self.assertEqual(read_response.status_code, 404)

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_task_updated_public_payload(self):
        notification = self.make_notification(
            event_type=Notification.EventType.TASK_UPDATED,
        )

        notification.payload = {
            "changed_fields": ["status", "title", "status"],
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {"changed_fields": ["status", "title"]},
        )
        self.assertNotIn("private-value", str(response.data))

    def test_comment_mention_public_payload(self):
        notification = self.make_notification(
            event_type=Notification.EventType.COMMENT_MENTIONED,
        )

        comment_id = str(uuid4())

        notification.payload = {
            "comment_id": comment_id,
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {"comment_id": comment_id},
        )

    def test_comment_reply_public_payload(self):
        notification = self.make_notification(
            event_type=Notification.EventType.COMMENT_REPLIED,
        )

        comment_id = str(uuid4())
        parent_id = str(uuid4())

        notification.payload = {
            "comment_id": comment_id,
            "parent_comment_id": parent_id,
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {
                "comment_id": comment_id,
                "parent_comment_id": parent_id,
            },
        )

    def test_workspace_invitation_public_payload(self):
        invitation = WorkspaceInvitation.objects.create(
            workspace=self.workspace,
            email=self.user.email,
            invited_by=self.actor,
            token_hash=uuid4().hex,
            expires_at=timezone.now() + timedelta(days=7),
        )

        notification = self.make_notification(
            event_type=Notification.EventType.WORKSPACE_INVITED,
        )

        notification.payload = {
            "invitation_id": str(invitation.pk),
            "invitation_token": "private-token",
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {"invitation_id": str(invitation.pk)},
        )
        self.assertNotIn("private-token", str(response.data))

    def test_workspace_role_changed_public_payload(self):
        notification = self.make_notification(
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )

        notification.payload = {
            "old_role": "member",
            "new_role": "admin",
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {
                "old_role": "member",
                "new_role": "admin",
            },
        )

    def test_invalid_public_payload_values_are_hidden(self):
        notification = self.make_notification(
            event_type=Notification.EventType.COMMENT_MENTIONED,
        )

        notification.payload = {
            "comment_id": "not-a-valid-uuid",
            "secret": "private-value",
        }
        notification.save(update_fields=["payload"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["payload"],
            {},
        )
        self.assertNotIn("private-value", str(response.data))

    def make_invitation_notification(self):
        invitation = WorkspaceInvitation.objects.create(
            workspace=self.workspace,
            email=self.user.email,
            invited_by=self.actor,
            token_hash=uuid4().hex,
            expires_at=timezone.now() + timedelta(days=7),
        )

        notification = self.make_notification(
            event_type=Notification.EventType.WORKSPACE_INVITED,
        )
        notification.payload = {
            "invitation_id": str(invitation.pk),
        }
        notification.save(update_fields=["payload"])

        return invitation, notification

    def test_pending_invitation_is_visible(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        self.workspace_membership.delete()

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(notification.pk),
        )
        self.assertEqual(
            count_response.data["unread_count"],
            1,
        )

    def test_inactive_invitation_statuses_are_hidden(self):
        for invitation_status in (
            WorkspaceInvitation.Status.ACCEPTED,
            WorkspaceInvitation.Status.REVOKED,
            WorkspaceInvitation.Status.EXPIRED,
        ):
            with self.subTest(status=invitation_status):
                invitation, notification = (
                    self.make_invitation_notification()
                )

                invitation.status = invitation_status
                invitation.save(update_fields=["status"])

                response = self.client.get(self.list_url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 0)

                invitation.delete()
                notification.delete()

    def test_expired_pending_invitation_is_hidden(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        invitation.expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        invitation.save(update_fields=["expires_at"])

        response = self.client.get(self.list_url)
        count_response = self.client.get(self.count_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            count_response.data["unread_count"],
            0,
        )

    def test_deleted_invitation_notification_is_hidden(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        invitation.delete()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_invitation_for_different_email_is_hidden(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        invitation.email = self.other_user.email
        invitation.save(update_fields=["email"])

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_inactive_invitation_cannot_be_marked_read(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        invitation.status = WorkspaceInvitation.Status.REVOKED
        invitation.save(update_fields=["status"])

        url = reverse(
            "notification-mark-read",
            kwargs={"pk": notification.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_mark_all_read_skips_inactive_invitation(self):
        invitation, notification = (
            self.make_invitation_notification()
        )

        invitation.status = WorkspaceInvitation.Status.REVOKED
        invitation.save(update_fields=["status"])

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["updated_count"],
            0,
        )

        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)
