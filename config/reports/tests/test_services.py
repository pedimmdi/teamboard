
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from projects.models import Project, ProjectMembership
from reports.services import get_project_report
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


class ProjectReportServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            email="report-manager@example.com",
            password="Test-password-123!",
        )
        cls.member = User.objects.create_user(
            email="report-member@example.com",
            password="Test-password-123!",
        )

        cls.workspace = Workspace.objects.create(
            name="Reports Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.manager,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="Reports Project",
            created_by=cls.manager,
        )

        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.manager,
            role=ProjectMembership.Role.MANAGER,
        )
        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.member,
            role=ProjectMembership.Role.MEMBER,
        )

    def test_empty_project_report(self):
        report = get_project_report(
            project=self.project,
        )

        self.assertEqual(
            report["summary"]["total_tasks"], 0
        )
        self.assertEqual(
            report["summary"]["completion_rate"], 0.0
        )
        self.assertEqual(
            len(report["member_workload"]), 2
        )
        self.assertTrue(
            all(
                row["total_tasks"] == 0
                for row in report["member_workload"]
            )
        )

    def test_project_statistics(self):
        today = timezone.localdate()

        Task.objects.create(
            project=self.project,
            title="Completed task",
            status=Task.Status.DONE,
            assignee=self.member,
            due_date=today - timedelta(days=2),
        )
        Task.objects.create(
            project=self.project,
            title="Overdue task",
            status=Task.Status.IN_PROGRESS,
            assignee=self.member,
            due_date=today - timedelta(days=1),
        )
        Task.objects.create(
            project=self.project,
            title="Unassigned task",
            status=Task.Status.TODO,
        )

        report = get_project_report(
            project=self.project,
            today=today,
        )

        summary = report["summary"]

        self.assertEqual(summary["total_tasks"], 3)
        self.assertEqual(summary["completed_tasks"], 1)
        self.assertEqual(summary["active_tasks"], 2)
        self.assertEqual(summary["overdue_tasks"], 1)
        self.assertEqual(summary["unassigned_tasks"], 0)
        self.assertAlmostEqual(
            summary["completion_rate"], 33.33
        )

        self.assertEqual(
            report["status_distribution"]["done"], 1
        )
        self.assertEqual(
            report["priority_distribution"]["medium"], 3
        )

        member_row = next(
            row for row in report["member_workload"]
            if row["user_id"] == self.member.pk
        )
        self.assertEqual(member_row["total_tasks"], 2)
        self.assertEqual(member_row["completed_tasks"], 1)
        self.assertEqual(member_row["overdue_tasks"], 1)

    def test_due_today_is_not_overdue(self):
        today = timezone.localdate()

        Task.objects.create(
            project=self.project,
            title="Due today",
            due_date=today,
            status=Task.Status.TODO,
        )

        report = get_project_report(
            project=self.project,
            today=today,
        )

        self.assertEqual(
            report["summary"]["overdue_tasks"], 0
        )

    def test_completed_task_is_not_overdue(self):
        today = timezone.localdate()

        Task.objects.create(
            project=self.project,
            title="Completed in the past",
            status=Task.Status.DONE,
            due_date=today - timedelta(days=5),
        )

        report = get_project_report(
            project=self.project,
            today=today,
        )

        self.assertEqual(
            report["summary"]["completed_tasks"], 1
        )
        self.assertEqual(
            report["summary"]["overdue_tasks"], 0
        )

    def test_task_assigned_to_former_member_is_still_counted(self):
        task = Task.objects.create(
            project=self.project,
            title="Former member task",
            assignee=self.member,
        )

        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).delete()

        task.refresh_from_db()

        report = get_project_report(
            project=self.project,
        )

        self.assertEqual(
            report["summary"]["total_tasks"], 1
        )

        self.assertEqual(
            report["summary"]["unassigned_tasks"],
            1 if task.assignee_id is None else 0,
        )

        self.assertFalse(
            any(
                row["user_id"] == self.member.pk
                for row in report["member_workload"]
            )
        )
