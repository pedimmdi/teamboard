from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from calendars.models import CalendarEvent
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class CalendarTimelineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="timeline-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="timeline-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="timeline-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Timeline Workspace",
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

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Timeline Project",
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

        self.start = datetime(
            2027, 6, 1, tzinfo=timezone.utc
        )
        self.end = self.start + timedelta(days=7)

        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

        self.project_url = reverse(
            "workspaces_api_v1:project-calendar-timeline",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
            },
        )
        self.workspace_url = reverse(
            "workspaces_api_v1:workspace-calendar-timeline",
            kwargs={"slug": self.workspace.slug},
        )

    def params(self, **overrides):
        data = {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }
        data.update(overrides)
        return data

    def create_event(self, project=None):
        return CalendarEvent.objects.create(
            project=project or self.project,
            title="Team Meeting",
            starts_at=self.start + timedelta(days=1),
            ends_at=self.start + timedelta(days=1, hours=1),
            created_by=self.owner,
        )

    def create_task(self, project=None, due_date=None):
        return Task.objects.create(
            project=project or self.project,
            title="Finish Report",
            due_date=due_date or (
                self.start + timedelta(days=2)
            ).date(),
            created_by=self.owner,
        )

    def test_timeline_combines_events_and_tasks(self):
        event = self.create_event()
        task = self.create_task()

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)

        items = response.data["results"]
        self.assertEqual(
            {item["item_type"] for item in items},
            {"event", "task"},
        )
        self.assertEqual(
            {item["id"] for item in items},
            {str(event.pk), str(task.pk)},
        )

    def test_timeline_excludes_tasks_without_due_date(self):
        self.create_task()
        Task.objects.create(
            project=self.project,
            title="Unscheduled Task",
            created_by=self.owner,
        )

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_timeline_filters_date_range(self):
        self.create_event()
        self.create_task(
            due_date=(self.end + timedelta(days=3)).date()
        )

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_timeline_requires_dates(self):
        response = self.client.get(self.project_url)
        self.assertEqual(response.status_code, 400)

    def test_timeline_rejects_large_range(self):
        response = self.client.get(
            self.project_url,
            self.params(
                end=(
                    self.start + timedelta(days=94)
                ).isoformat()
            ),
        )
        self.assertEqual(response.status_code, 400)

    def test_outsider_cannot_access_project_timeline(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(
            self.project_url,
            self.params(),
        )
        self.assertEqual(response.status_code, 404)

    def test_workspace_timeline_hides_private_projects(self):
        visible = self.create_event()

        private_project = Project.objects.create(
            workspace=self.workspace,
            name="Private Timeline Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=private_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        private = self.create_event(project=private_project)

        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            self.workspace_url,
            self.params(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(visible.pk)},
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.workspace_url,
            self.params(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(visible.pk), str(private.pk)},
        )

    def test_project_timeline_excludes_other_projects(self):
        self.create_event()
        self.create_task()

        other_project = Project.objects.create(
            workspace=self.workspace,
            name="Other Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=other_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        other_event = self.create_event(project=other_project)
        other_task = self.create_task(project=other_project)

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        returned_ids = {
            item["id"] for item in response.data["results"]
        }
        self.assertNotIn(str(other_event.pk), returned_ids)
        self.assertNotIn(str(other_task.pk), returned_ids)
        self.assertEqual(response.data["count"], 2)

    def test_timeline_task_date_boundaries(self):
        first_task = self.create_task(
            due_date=self.start.date()
        )
        self.create_task(
            due_date=self.end.date()
        )

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(first_task.pk),
        )

    def test_timeline_rejects_duplicate_dates(self):
        response = self.client.get(
            self.project_url
            + "?start=2027-06-01T00:00:00Z"
            + "&start=2027-06-02T00:00:00Z"
            + "&end=2027-06-08T00:00:00Z"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("start", response.data)

    def test_timeline_rejects_unknown_query_params(self):
        response = self.client.get(
            self.project_url,
            self.params(unexpected="value"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("query", response.data)

    def test_timeline_normalizes_timezone_offsets(self):
        first_task = self.create_task(
            due_date=self.start.date()
        )
        self.create_task(
            due_date=self.end.date()
        )

        response = self.client.get(
            self.project_url,
            {
                "start": "2027-06-01T03:30:00+03:30",
                "end": "2027-06-08T03:30:00+03:30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(first_task.pk),
        )

    def test_timeline_excludes_task_before_partial_day(self):
        self.create_task(
            due_date=self.start.date()
        )
        next_day_task = self.create_task(
            due_date=(
                self.start + timedelta(days=1)
            ).date()
        )

        response = self.client.get(
            self.project_url,
            {
                "start": (
                    self.start + timedelta(hours=12)
                ).isoformat(),
                "end": self.end.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(next_day_task.pk),
        )

    def test_timeline_includes_task_before_partial_end(self):
        task = self.create_task(
            due_date=self.end.date()
        )

        response = self.client.get(
            self.project_url,
            {
                "start": self.start.isoformat(),
                "end": (
                    self.end + timedelta(hours=12)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(task.pk),
        )

    def test_timeline_rejects_reversed_dates(self):
        response = self.client.get(
            self.project_url,
            {
                "start": self.end.isoformat(),
                "end": self.start.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("end", response.data)

    def test_timeline_rejects_equal_dates(self):
        response = self.client.get(
            self.project_url,
            {
                "start": self.start.isoformat(),
                "end": self.start.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("end", response.data)

    def test_workspace_timeline_hides_private_tasks(self):
        visible_task = self.create_task()

        private_project = Project.objects.create(
            workspace=self.workspace,
            name="Private Tasks Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=private_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        private_task = self.create_task(
            project=private_project,
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            self.workspace_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                item["id"]
                for item in response.data["results"]
            },
            {str(visible_task.pk)},
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.workspace_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                item["id"]
                for item in response.data["results"]
            },
            {
                str(visible_task.pk),
                str(private_task.pk),
            },
        )

    def test_timeline_accepts_500_tasks(self):
        Task.objects.bulk_create([
            Task(
                project=self.project,
                title=f"Bulk Task {index}",
                due_date=self.start.date(),
                created_by=self.owner,
            )
            for index in range(500)
        ])

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(
            response.status_code,
            200,
            response.data,
        )
        self.assertEqual(response.data["count"], 500)
        self.assertEqual(
            len(response.data["results"]),
            500,
        )

    def test_timeline_rejects_more_than_500_tasks(self):
        Task.objects.bulk_create([
            Task(
                project=self.project,
                title=f"Overflow Task {index}",
                due_date=self.start.date(),
                created_by=self.owner,
            )
            for index in range(501)
        ])

        response = self.client.get(
            self.project_url,
            self.params(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date_range", response.data)

    def test_timeline_query_count_is_bounded(self):
        Task.objects.bulk_create([
            Task(
                project=self.project,
                title=f"Performance Task {index}",
                due_date=self.start.date(),
                created_by=self.owner,
            )
            for index in range(50)
        ])

        self.create_event()

        # Authentication and permission queries are included.
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                self.project_url,
                self.params(),
            )

        self.assertEqual(
            response.status_code,
            200,
            response.data,
        )
        self.assertEqual(response.data["count"], 51)

        self.assertLessEqual(
            len(queries),
            15,
            f"Timeline executed {len(queries)} queries.",
        )
