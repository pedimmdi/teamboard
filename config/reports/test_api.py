
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


class ProjectReportAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="reports-owner@example.com",
            password="Test-password-123!",
        )
        cls.member = User.objects.create_user(
            email="reports-member@example.com",
            password="Test-password-123!",
        )
        cls.outsider = User.objects.create_user(
            email="reports-outsider@example.com",
            password="Test-password-123!",
        )

        cls.workspace = Workspace.objects.create(
            name="API Reports Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.owner,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=cls.workspace,
            user=cls.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="API Reports Project",
            created_by=cls.owner,
        )
        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        ProjectMembership.objects.create(
            project=cls.project,
            user=cls.member,
            role=ProjectMembership.Role.MEMBER,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = reverse(
            "workspaces_api_v1:reports_project_api_v1:project-report",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
            },
        )

    def test_member_can_view_project_report(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 0
        )

    def test_outsider_cannot_view_report(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_view_report(self):
        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))

    def test_report_is_read_only(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 405)

    def test_workspace_member_without_project_membership_is_denied(self):
        workspace_only_user = User.objects.create_user(
            email="workspace-only-report@example.com",
            password="Test-password-123!",
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=workspace_only_user,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.client.force_authenticate(
            user=workspace_only_user
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_workspace_owner_without_project_membership_can_view(self):
        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).update(role=ProjectMembership.Role.MANAGER)

        ProjectMembership.objects.filter(
            project=self.project,
            user=self.owner,
        ).delete()

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_project_report_rejects_wrong_workspace_slug(self):
        other_workspace = Workspace.objects.create(
            name="Another Reports Workspace",
        )

        wrong_url = reverse(
            "workspaces_api_v1:reports_project_api_v1:project-report",
            kwargs={
                "slug": other_workspace.slug,
                "project_id": self.project.pk,
            },
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(wrong_url)

        self.assertEqual(response.status_code, 404)

    def test_history_records_bulk_transitions_and_preserves_original_assignee(self):
        from django.db import transaction
        from tasks.models import Task, TaskStatusHistory

        task = Task.objects.create(project=self.project, title="History", assignee=self.member)
        Task.objects.filter(pk=task.pk).update(status="done")
        task.refresh_from_db()
        first_completion = task.completed_at
        self.assertIsNotNone(first_completion)
        Task.objects.filter(pk=task.pk).update(assignee=self.owner)
        task.refresh_from_db()
        self.assertEqual(task.completed_at, first_completion)

        task.status = "todo"
        Task.objects.bulk_update([task], ["status"])
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)
        with transaction.atomic():
            Task.objects.filter(pk=task.pk).update(status="done")
            transaction.set_rollback(True)
        task.refresh_from_db()
        self.assertEqual(task.status, "todo")
        self.assertEqual(TaskStatusHistory.objects.filter(task_id=task.pk).count(), 3)

        task.delete()
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url + "history/", {
            "period": "7d", "assignee": self.member.pk, "granularity": "week",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum(row["created"] for row in response.data["results"]), 1)
        self.assertEqual(sum(row["completed"] for row in response.data["results"]), 1)
        self.assertIsNotNone(response.data["completion_tracking_since"])

    def test_advanced_reports_filter_validate_and_escape_csv(self):
        import csv
        from datetime import timedelta
        from io import StringIO
        from unittest.mock import patch

        from django.utils import timezone
        from tasks.models import Task

        Task.objects.create(
            project=self.project, title=" =1+1", priority="urgent",
            due_date=timezone.localdate() + timedelta(days=2),
        )
        Task.objects.create(project=self.project, title="Other", priority="low")
        self.client.force_authenticate(user=self.owner)
        query = {"priority": "urgent", "assignee": "unassigned"}
        result = self.client.get(self.url + "workload/", query)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data[0]["due_soon_tasks"], 1)
        self.assertIsNone(result.data[0]["assignee"])
        result = self.client.get(self.url + "export/", query)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.content.startswith(b"\xef\xbb\xbfsep=,\r\n"))
        rows = list(csv.reader(StringIO(result.content.decode("utf-8-sig").split("\r\n", 1)[1])))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][2], "' =1+1")
        with patch("reports.api.v1.analytics_views.CSV_ROW_LIMIT", 1):
            self.assertEqual(self.client.get(self.url + "export/").status_code, 400)
        for query in (
            {"start_date": "2025-01-01"}, {"assignee": "9999999999999999999"},
            {"start_date": "2024-01-01", "end_date": "2026-01-01"},
        ):
            self.assertEqual(self.client.get(self.url + "history/", query).status_code, 400)

    def test_workspace_ranking_and_export_hide_private_projects(self):
        from tasks.models import Task

        private = Project.objects.create(workspace=self.workspace, name="Private", created_by=self.owner)
        ProjectMembership.objects.create(project=private, user=self.owner, role="manager")
        Task.objects.create(project=private, title="Private task")
        Task.objects.create(project=self.project, title="Visible task", status="done")
        workspace_url = reverse(
            "workspaces_api_v1:reports_api_v1:workspace-report", kwargs={"slug": self.workspace.slug},
        )
        self.client.force_authenticate(user=self.member)
        ranking = self.client.get(workspace_url + "projects/", {"page_size": 1, "ordering": "-completed_tasks"})
        self.assertEqual(ranking.status_code, 200)
        self.assertEqual(ranking.data["count"], 1)
        self.assertEqual(ranking.data["results"][0]["completed_tasks"], 1)
        export = self.client.get(workspace_url + "export/")
        self.assertContains(export, "Visible task")
        self.assertNotContains(export, "Private task")
        self.client.force_authenticate(user=self.outsider)
        for url in ("history/", "workload/", "export/", "projects/"):
            self.assertEqual(self.client.get(workspace_url + url).status_code, 404)

    def test_history_query_count_does_not_grow_with_bucket_count(self):
        self.client.force_authenticate(user=self.owner)

        def query_count(period):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.url + "history/", {"period": period})
            self.assertEqual(response.status_code, 200)
            return len(queries)

        short_range = query_count("7d")
        self.assertEqual(query_count("90d"), short_range)
        self.assertLessEqual(short_range, 10)

    def test_weekly_buckets_expose_partial_and_full_calendar_weeks(self):
        from datetime import datetime, timezone
        from tasks.models import TaskStatusHistory

        self.client.force_authenticate(user=self.owner)
        for day in (2, 7, 9):
            TaskStatusHistory.objects.create(
                project=self.project, task_id=uuid4(),
                previous_status="todo", status="done", priority="medium",
                changed_at=datetime(2026, 11, day, 12, tzinfo=timezone.utc),
            )
        response = self.client.get(self.url + "history/", {
            "start_date": "2026-11-04", "end_date": "2026-11-10", "granularity": "week",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [
            {"date": "2026-11-02", "start_date": "2026-11-04", "end_date": "2026-11-08", "created": 0, "completed": 1},
            {"date": "2026-11-09", "start_date": "2026-11-09", "end_date": "2026-11-10", "created": 0, "completed": 1},
        ])
        response = self.client.get(self.url + "history/", {
            "start_date": "2026-11-02", "end_date": "2026-11-08", "granularity": "week",
        })
        self.assertEqual(response.data["results"][0]["completed"], 2)
        self.assertEqual(response.data["results"][0]["start_date"], "2026-11-02")
        self.assertEqual(response.data["results"][0]["end_date"], "2026-11-08")

    def test_all_report_endpoints_enforce_project_visibility_for_each_workspace_role(self):
        from tasks.models import Task

        private = Project.objects.create(workspace=self.workspace, name="Hidden", created_by=self.owner)
        ProjectMembership.objects.create(project=private, user=self.owner, role="manager")
        Task.objects.create(project=private, title="داده خصوصی")
        base = f"/api/v1/workspaces/{self.workspace.slug}/projects/{private.pk}/reports/"
        workspace_base = f"/api/v1/workspaces/{self.workspace.slug}/reports/"
        admin = User.objects.create_user(email="report-admin@example.com")
        WorkspaceMembership.objects.create(user=admin, workspace=self.workspace, role="admin")
        for role, user in (("member", self.member), ("admin", admin), ("owner", self.owner)):
            self.client.force_authenticate(user=user)
            for suffix in ("", "history/", "workload/", "export/"):
                with self.subTest(role=role, endpoint=suffix):
                    self.assertEqual(self.client.get(base + suffix).status_code, 404 if role == "member" else 200)
            ranking = self.client.get(workspace_base + "projects/")
            expected = 1 if role == "member" else 2
            self.assertEqual(ranking.data["count"], expected)
            export = self.client.get(workspace_base + "export/")
            self.assertEqual(export.status_code, 200)
            self.assertEqual("داده خصوصی" in export.content.decode("utf-8-sig"), role != "member")
