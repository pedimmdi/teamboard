
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from projects.models import Project, ProjectMembership
from reports.services import (
    get_project_report,
    get_workspace_report,
)
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


class ReportsPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="reports-performance@example.com",
            password="Test-password-123!",
        )
        cls.workspace = Workspace.objects.create(
            name="Performance Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="Performance Project",
            created_by=cls.user,
        )
        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.user,
            role=ProjectMembership.Role.MANAGER,
        )

    def test_project_report_query_count_does_not_grow_with_tasks(self):
        with CaptureQueriesContext(connection) as queries:
            get_project_report(project=self.project)

        baseline_count = len(queries)
        self.assertLessEqual(baseline_count, 3)

        Task.objects.bulk_create([
            Task(
                project=self.project,
                title=f"Performance task {i}",
            )
            for i in range(100)
        ])

        with CaptureQueriesContext(connection) as queries:
            report = get_project_report(project=self.project)

        self.assertEqual(
            report["summary"]["total_tasks"], 100
        )
        self.assertEqual(
            len(queries), baseline_count
        )

    def test_workspace_report_query_count_does_not_grow_with_projects(self):
        with CaptureQueriesContext(connection) as queries:
            get_workspace_report(
                workspace=self.workspace,
                user=self.user,
            )

        baseline_count = len(queries)
        self.assertLessEqual(baseline_count, 3)

        projects = Project.objects.bulk_create([
            Project(
                workspace=self.workspace,
                name=f"Performance Project {i}",
                created_by=self.user,
            )
            for i in range(20)
        ])

        ProjectMembership.objects.bulk_create([
            ProjectMembership(
                project=project,
                user=self.user,
                role=ProjectMembership.Role.MANAGER,
            )
            for project in projects
        ])

        Task.objects.bulk_create([
            Task(
                project=project,
                title="Performance task",
            )
            for project in projects
        ])

        with CaptureQueriesContext(connection) as queries:
            report = get_workspace_report(
                workspace=self.workspace,
                user=self.user,
            )

        self.assertEqual(report["total_projects"], 21)
        self.assertEqual(
            report["summary"]["total_tasks"], 20
        )
        self.assertEqual(
            len(queries), baseline_count
        )
