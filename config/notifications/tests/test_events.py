
from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.events import notify_task_assigned
from notifications.models import Notification
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskAssignedNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user(
            email="assignment-actor@example.com",
            password="TestPassword123!",
        )
        cls.recipient = User.objects.create_user(
            email="assignment-recipient@example.com",
            password="TestPassword123!",
        )

        cls.workspace = Workspace.objects.create(
            name="Assignment Notification Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.actor,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.recipient,
            role=WorkspaceMembership.Role.MEMBER,
        )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="Assignment Notification Project",
            created_by=cls.actor,
        )

        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.actor,
            role=ProjectMembership.Role.MANAGER,
        )
        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.recipient,
            role=ProjectMembership.Role.MEMBER,
        )

        cls.task = Task.objects.create(
            project=cls.project,
            title="Assignment Notification Task",
            created_by=cls.actor,
            assignee=cls.recipient,
        )

    def test_assignment_creates_notification(self):
        notification, created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        self.assertTrue(created)
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.count(), 1)

        self.assertEqual(
            notification.event_type,
            Notification.EventType.TASK_ASSIGNED,
        )
        self.assertEqual(
            notification.recipient_id,
            self.recipient.pk,
        )
        self.assertEqual(
            notification.actor_id,
            self.actor.pk,
        )

    def test_assignment_has_correct_scope(self):
        notification, created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        self.assertTrue(created)
        self.assertEqual(
            notification.workspace_id,
            self.workspace.pk,
        )
        self.assertEqual(
            notification.project_id,
            self.project.pk,
        )
        self.assertEqual(
            notification.task_id,
            self.task.pk,
        )
        self.assertEqual(notification.payload, {})

    def test_unassigned_task_creates_no_notification(self):
        self.task.assignee = None
        self.task.save(update_fields=["assignee"])

        notification, created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        self.assertIsNone(notification)
        self.assertFalse(created)
        self.assertFalse(Notification.objects.exists())

    def test_self_assignment_creates_no_notification(self):
        self.task.assignee = self.actor
        self.task.save(update_fields=["assignee"])

        notification, created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        self.assertIsNone(notification)
        self.assertFalse(created)
        self.assertFalse(Notification.objects.exists())

    def test_separate_assignment_events_have_unique_keys(self):
        first, first_created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        second, second_created = notify_task_assigned(
            task=self.task,
            actor=self.actor,
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(
            first.deduplication_key,
            second.deduplication_key,
        )
        self.assertEqual(Notification.objects.count(), 2)
