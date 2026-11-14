from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from notifications.models import Notification
from projects.models import Project, ProjectMembership
from tasks.models import Task
from tasks.services import create_task, update_task, delete_task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="service-owner@example.com",
            password="Strong-password-2026!",
        )
        self.admin = User.objects.create_user(
            email="service-admin@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="service-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="service-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Task Service Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.admin, WorkspaceMembership.Role.ADMIN),
            (self.member, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Task Service Project",
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

    def make_task(self, **kwargs):
        return create_task(
            project=self.project,
            actor=self.owner,
            title=kwargs.pop("title", "Example Task"),
            **kwargs,
        )

    def test_owner_can_create_task(self):
        task = self.make_task()

        self.assertEqual(task.project, self.project)
        self.assertEqual(task.created_by, self.owner)
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_project_member_can_create_task(self):
        task = create_task(
            project=self.project,
            actor=self.member,
            title="Member Task",
        )

        self.assertEqual(task.created_by, self.member)

    def test_workspace_admin_can_create_without_project_membership(self):
        task = create_task(
            project=self.project,
            actor=self.admin,
            title="Admin Task",
        )

        self.assertEqual(task.created_by, self.admin)

    def test_outsider_cannot_create_task(self):
        with self.assertRaises(Http404):
            create_task(
                project=self.project,
                actor=self.outsider,
                title="Unauthorized Task",
            )

        self.assertFalse(
            Task.objects.filter(
                title="Unauthorized Task",
            ).exists()
        )

    def test_task_title_is_trimmed(self):
        task = self.make_task(
            title="  Backend Task  ",
        )

        self.assertEqual(task.title, "Backend Task")

    def test_blank_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_task(title="   ")

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_task(status="invalid")

    def test_invalid_priority_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_task(priority="invalid")

    def test_non_member_assignee_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_task(assignee=self.outsider)

    def test_project_member_can_be_assigned(self):
        task = self.make_task(
            assignee=self.member,
        )

        self.assertEqual(task.assignee, self.member)

    def test_create_task_with_assignee_creates_notification(self):
        task = self.make_task(
            assignee=self.member,
        )

        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.TASK_ASSIGNED,
        )
        self.assertEqual(notification.recipient_id, self.member.pk)
        self.assertEqual(notification.actor_id, self.owner.pk)
        self.assertEqual(notification.workspace_id, self.workspace.pk)
        self.assertEqual(notification.project_id, self.project.pk)
        self.assertEqual(notification.task_id, task.pk)

    def test_create_task_without_assignee_creates_no_notification(self):
        self.make_task()

        self.assertFalse(Notification.objects.exists())

    def test_create_task_self_assignment_creates_no_notification(self):
        task = self.make_task(
            assignee=self.owner,
        )

        self.assertEqual(task.assignee_id, self.owner.pk)
        self.assertFalse(Notification.objects.exists())

    def test_create_task_rolls_back_if_notification_fails(self):
        with patch(
            "tasks.services.notify_task_assigned",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                self.make_task(
                    title="Rollback Assignment Task",
                    assignee=self.member,
                )

        self.assertFalse(
            Task.objects.filter(
                title="Rollback Assignment Task",
            ).exists()
        )
        self.assertFalse(Notification.objects.exists())

    def test_update_assigns_unassigned_task_and_notifies(self):
        task = self.make_task()

        update_task(
            task=task,
            actor=self.owner,
            assignee=self.member,
            update_assignee=True,
        )

        task.refresh_from_db()

        self.assertEqual(task.assignee_id, self.member.pk)
        self.assertEqual(Notification.objects.count(), 1)

        notification = Notification.objects.get()
        self.assertEqual(
            notification.event_type,
            Notification.EventType.TASK_ASSIGNED,
        )
        self.assertEqual(notification.recipient_id, self.member.pk)
        self.assertEqual(notification.actor_id, self.owner.pk)
        self.assertEqual(notification.task_id, task.pk)

    def test_update_changes_assignee_and_notifies_new_user(self):
        task = self.make_task(assignee=self.member)
        initial_notification = Notification.objects.get()

        update_task(
            task=task,
            actor=self.admin,
            assignee=self.owner,
            update_assignee=True,
        )

        task.refresh_from_db()

        self.assertEqual(task.assignee_id, self.owner.pk)
        self.assertEqual(Notification.objects.count(), 2)

        new_notification = Notification.objects.exclude(
            pk=initial_notification.pk,
        ).get()

        self.assertEqual(new_notification.recipient_id, self.owner.pk)
        self.assertEqual(new_notification.actor_id, self.admin.pk)
        self.assertEqual(new_notification.task_id, task.pk)

        self.assertTrue(
            Notification.objects.filter(
                pk=initial_notification.pk,
                recipient=self.member,
            ).exists()
        )

    def test_update_same_assignee_does_not_notify_again(self):
        task = self.make_task(assignee=self.member)
        original_notification = Notification.objects.get()

        update_task(
            task=task,
            actor=self.owner,
            assignee=self.member,
            update_assignee=True,
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertTrue(
            Notification.objects.filter(
                pk=original_notification.pk,
            ).exists()
        )

    def test_update_clear_assignee_does_not_notify(self):
        task = self.make_task(assignee=self.member)

        update_task(
            task=task,
            actor=self.owner,
            assignee=None,
            update_assignee=True,
        )

        task.refresh_from_db()

        self.assertIsNone(task.assignee_id)
        self.assertEqual(Notification.objects.count(), 1)

    def test_update_other_fields_does_not_notify_again(self):
        task = self.make_task(assignee=self.member)

        update_task(
            task=task,
            actor=self.owner,
            title="Changed without reassignment",
            status=Task.Status.IN_PROGRESS,
        )

        task.refresh_from_db()

        self.assertEqual(
            task.title,
            "Changed without reassignment",
        )
        self.assertEqual(Notification.objects.count(), 1)

    def test_update_self_assignment_does_not_notify(self):
        task = self.make_task()

        update_task(
            task=task,
            actor=self.owner,
            assignee=self.owner,
            update_assignee=True,
        )

        task.refresh_from_db()

        self.assertEqual(task.assignee_id, self.owner.pk)
        self.assertFalse(Notification.objects.exists())

    def test_update_rolls_back_when_notification_fails(self):
        task = self.make_task()
        original_title = task.title

        with patch(
            "tasks.services.notify_task_assigned",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                update_task(
                    task=task,
                    actor=self.owner,
                    title="Should be rolled back",
                    assignee=self.member,
                    update_assignee=True,
                )

        task.refresh_from_db()

        self.assertEqual(task.title, original_title)
        self.assertIsNone(task.assignee_id)
        self.assertFalse(Notification.objects.exists())

    def test_update_task_changes_selected_fields(self):
        task = self.make_task(
            description="Original description",
        )

        updated = update_task(
            task=task,
            actor=self.owner,
            title="Updated Task",
            status=Task.Status.IN_PROGRESS,
        )

        updated.refresh_from_db()

        self.assertEqual(updated.title, "Updated Task")
        self.assertEqual(
            updated.status,
            Task.Status.IN_PROGRESS,
        )
        self.assertEqual(
            updated.description,
            "Original description",
        )

    def test_update_preserves_assignee_when_omitted(self):
        task = self.make_task(
            assignee=self.member,
        )

        update_task(
            task=task,
            actor=self.owner,
            status=Task.Status.DONE,
        )

        task.refresh_from_db()
        self.assertEqual(task.assignee, self.member)

    def test_update_can_clear_assignee(self):
        task = self.make_task(
            assignee=self.member,
        )

        update_task(
            task=task,
            actor=self.owner,
            assignee=None,
            update_assignee=True,
        )

        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_update_can_clear_due_date(self):
        task = self.make_task(
            due_date=date(2026, 12, 1),
        )

        update_task(
            task=task,
            actor=self.owner,
            due_date=None,
            update_due_date=True,
        )

        task.refresh_from_db()
        self.assertIsNone(task.due_date)

    def test_update_preserves_due_date_when_omitted(self):
        expected_date = date(2026, 12, 1)
        task = self.make_task(
            due_date=expected_date,
        )

        update_task(
            task=task,
            actor=self.owner,
            title="New Title",
        )

        task.refresh_from_db()
        self.assertEqual(task.due_date, expected_date)

    def test_update_rejects_invalid_assignee(self):
        task = self.make_task()

        with self.assertRaises(ValidationError):
            update_task(
                task=task,
                actor=self.owner,
                assignee=self.outsider,
                update_assignee=True,
            )

        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_project_member_can_update_task(self):
        task = self.make_task()

        update_task(
            task=task,
            actor=self.member,
            title="Member Updated",
        )

        task.refresh_from_db()
        self.assertEqual(task.title, "Member Updated")

    def test_outsider_cannot_update_task(self):
        task = self.make_task()

        with self.assertRaises(Http404):
            update_task(
                task=task,
                actor=self.outsider,
                title="Unauthorized Update",
            )

        task.refresh_from_db()
        self.assertEqual(task.title, "Example Task")

    def test_project_member_cannot_delete_task(self):
        task = self.make_task()

        with self.assertRaises(PermissionDenied):
            delete_task(
                task=task,
                actor=self.member,
            )

        self.assertTrue(
            Task.objects.filter(pk=task.pk).exists()
        )

    def test_project_manager_can_delete_task(self):
        task = self.make_task()
        task_id = task.pk

        delete_task(
            task=task,
            actor=self.owner,
        )

        self.assertFalse(
            Task.objects.filter(pk=task_id).exists()
        )

    def test_workspace_admin_can_delete_task(self):
        task = self.make_task()
        task_id = task.pk

        delete_task(
            task=task,
            actor=self.admin,
        )

        self.assertFalse(
            Task.objects.filter(pk=task_id).exists()
        )
