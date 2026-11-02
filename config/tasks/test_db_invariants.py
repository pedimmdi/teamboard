
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskDatabaseInvariantTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="task-db-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="task-db-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="task-db-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Task Database Workspace",
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

        with transaction.atomic():
            self.project = Project.objects.create(
                workspace=self.workspace,
                name="First Project",
                created_by=self.owner,
            )
            ProjectMembership.objects.create(
                project=self.project,
                user=self.owner,
                role=ProjectMembership.Role.MANAGER,
            )
            self.member_membership = (
                ProjectMembership.objects.create(
                    project=self.project,
                    user=self.member,
                    role=ProjectMembership.Role.MEMBER,
                )
            )

            self.other_project = Project.objects.create(
                workspace=self.workspace,
                name="Second Project",
                created_by=self.owner,
            )
            ProjectMembership.objects.create(
                project=self.other_project,
                user=self.owner,
                role=ProjectMembership.Role.MANAGER,
            )

    def make_task(self, *, assignee=None):
        return Task.objects.create(
            project=self.project,
            title="Database Task",
            assignee=assignee,
            created_by=self.owner,
        )

    def test_direct_orm_invalid_status_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task()
                Task.objects.filter(
                    project=self.project,
                ).update(status="invalid")

        self.assertFalse(
            Task.objects.filter(status="invalid").exists()
        )

    def test_direct_orm_invalid_priority_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task()
                Task.objects.filter(
                    project=self.project,
                ).update(priority="invalid")

        self.assertFalse(
            Task.objects.filter(priority="invalid").exists()
        )

    def test_cannot_move_task_to_another_project(self):
        task = self.make_task()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Task.objects.filter(pk=task.pk).update(
                    project=self.other_project,
                )

        task.refresh_from_db()
        self.assertEqual(task.project_id, self.project.pk)

    def test_cannot_assign_outsider_through_orm(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task(assignee=self.outsider)

        self.assertFalse(
            Task.objects.filter(
                assignee=self.outsider,
            ).exists()
        )

    def test_valid_project_member_can_be_assigned(self):
        task = self.make_task(assignee=self.member)

        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.pk)

    def test_removing_project_member_clears_assignee(self):
        task = self.make_task(assignee=self.member)

        with transaction.atomic():
            ProjectMembership.objects.filter(
                pk=self.member_membership.pk,
            ).delete()

        task.refresh_from_db()
        self.assertIsNone(task.assignee_id)

    def test_changing_membership_user_clears_old_assignee(self):
        task = self.make_task(assignee=self.member)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.filter(
                    pk=self.member_membership.pk,
                ).update(user=self.outsider)

        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.pk)

    def test_deferred_validation_uses_final_assignee(self):
        with transaction.atomic():
            task = self.make_task()

            Task.objects.filter(pk=task.pk).update(
                assignee=self.outsider,
            )
            Task.objects.filter(pk=task.pk).update(
                assignee=self.member,
            )

        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.pk)
