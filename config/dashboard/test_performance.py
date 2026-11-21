
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import User
from calendars.models import CalendarEvent
from notifications.models import Notification
from projects.models import Project, ProjectMembership
from tasks.models import Task, TaskReminder
from workspaces.models import Workspace, WorkspaceMembership


class DashboardPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="dashboard-performance@example.com",
        )

        cls.workspace = Workspace.objects.create(
            name="Dashboard Performance",
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

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.url = reverse(
            "workspaces_api_v1:dashboard_api_v1:overview",
            kwargs={"slug": self.workspace.slug},
        )

    def measure_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        return len(queries), response.data

    def create_dashboard_records(self, project, number, prefix):
        now = timezone.now()

        for index in range(number):
            task = Task.objects.create(
                project=project,
                title=f"{prefix} task {index}",
                created_by=self.user,
                assignee=self.user,
                due_date=timezone.localdate() + timedelta(days=2),
            )

            TaskReminder.objects.create(
                task=task,
                recipient=self.user,
                kind=TaskReminder.Kind.ABSOLUTE,
                timezone="UTC",
                run_at=now + timedelta(hours=index + 1),
            )

            starts_at = now + timedelta(hours=index + 1)

            CalendarEvent.objects.create(
                project=project,
                title=f"{prefix} event {index}",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
            )

            Notification.objects.create(
                recipient=self.user,
                actor=self.user,
                event_type=Notification.EventType.TASK_ASSIGNED,
                workspace=self.workspace,
                project=project,
                task=task,
            )

    def test_query_count_does_not_grow_with_records(self):
        # Warm up the API before capturing the baseline.
        self.measure_queries()

        baseline_count, _ = self.measure_queries()

        self.create_dashboard_records(
            project=self.project,
            number=12,
            prefix="Many records",
        )

        current_count, data = self.measure_queries()

        self.assertEqual(
            current_count,
            baseline_count,
            (
                "Dashboard query count increased as records grew. "
                "Check for N+1 queries."
            ),
        )

        self.assertEqual(data["my_tasks"]["count"], 12)
        self.assertEqual(
            data["upcoming_reminders"]["count"], 12
        )
        self.assertEqual(
            data["upcoming_events"]["count"], 12
        )
        self.assertEqual(
            data["recent_notifications"]["count"], 12
        )

        for section in (
            "my_tasks",
            "upcoming_reminders",
            "upcoming_events",
            "recent_notifications",
        ):
            self.assertEqual(
                len(data[section]["items"]),
                5,
            )

    def test_query_count_does_not_grow_with_projects(self):
        self.measure_queries()

        baseline_count, _ = self.measure_queries()

        for index in range(8):
            project = Project.objects.create(
                workspace=self.workspace,
                name=f"Scale Project {index}",
                created_by=self.user,
            )

            ProjectMembership.objects.create(
                project=project,
                user=self.user,
                role=ProjectMembership.Role.MANAGER,
            )

            self.create_dashboard_records(
                project=project,
                number=1,
                prefix=f"Project {index}",
            )

        current_count, data = self.measure_queries()

        self.assertEqual(
            current_count,
            baseline_count,
            (
                "Dashboard query count increased with project "
                "count. Check project-related queries."
            ),
        )

        self.assertEqual(data["projects"]["count"], 9)
        self.assertEqual(data["my_tasks"]["count"], 8)
        self.assertEqual(
            data["upcoming_reminders"]["count"], 8
        )
        self.assertEqual(
            data["upcoming_events"]["count"], 8
        )
        self.assertEqual(
            data["recent_notifications"]["count"], 8
        )

        for section in (
            "projects",
            "my_tasks",
            "upcoming_reminders",
            "upcoming_events",
            "recent_notifications",
        ):
            self.assertLessEqual(
                len(data[section]["items"]),
                5,
            )
