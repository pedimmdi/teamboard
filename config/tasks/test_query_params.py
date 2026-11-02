
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskQueryParameterTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="query-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="query-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="query-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Query Parameter Workspace",
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
            name="Query Parameter Project",
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

        self.url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
            },
        )

        today = date.today()

        self.todo = self.make_task(
            title="Build Login API",
            description="Authentication endpoint",
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
            assignee=self.member,
            due_date=today + timedelta(days=3),
        )

        self.progress = self.make_task(
            title="Write Backend Tests",
            description="Improve API coverage",
            status=Task.Status.IN_PROGRESS,
            priority=Task.Priority.URGENT,
            due_date=today + timedelta(days=1),
        )

        self.done = self.make_task(
            title="Update Documentation",
            description="Document authentication flow",
            status=Task.Status.DONE,
            priority=Task.Priority.LOW,
            assignee=self.member,
            due_date=today + timedelta(days=2),
        )

        self.client.force_authenticate(user=self.owner)

    def make_task(self, **kwargs):
        return Task.objects.create(
            project=self.project,
            created_by=self.owner,
            **kwargs,
        )

    def titles(self, response):
        return [
            task["title"]
            for task in response.data["results"]
        ]

    def test_filter_by_status(self):
        response = self.client.get(
            self.url,
            {"status": "in_progress"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Write Backend Tests"],
        )

    def test_filter_by_priority(self):
        response = self.client.get(
            self.url,
            {"priority": "high"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Build Login API"],
        )

    def test_filter_by_assignee(self):
        response = self.client.get(
            self.url,
            {"assignee": str(self.member.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            self.titles(response),
            [
                "Build Login API",
                "Update Documentation",
            ],
        )

    def test_filter_unassigned_true(self):
        response = self.client.get(
            self.url,
            {"unassigned": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Write Backend Tests"],
        )

    def test_filter_unassigned_false_keeps_all_tasks(self):
        response = self.client.get(
            self.url,
            {"unassigned": "false"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)

    def test_combined_filters(self):
        response = self.client.get(
            self.url,
            {
                "status": "todo",
                "priority": "high",
                "assignee": str(self.member.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Build Login API"],
        )

    def test_invalid_status_returns_400(self):
        response = self.client.get(
            self.url,
            {"status": "unknown"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_invalid_priority_returns_400(self):
        response = self.client.get(
            self.url,
            {"priority": "critical"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("priority", response.data)

    def test_invalid_assignee_uuid_returns_400(self):
        response = self.client.get(
            self.url,
            {"assignee": "not-a-uuid"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("assignee", response.data)

    def test_invalid_unassigned_returns_400(self):
        response = self.client.get(
            self.url,
            {"unassigned": "yes"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unassigned", response.data)

    def test_conflicting_assignee_filters_return_400(self):
        response = self.client.get(
            self.url,
            {
                "assignee": str(self.member.pk),
                "unassigned": "true",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unassigned", response.data)

    def test_search_matches_title_case_insensitively(self):
        response = self.client.get(
            self.url,
            {"search": "LOGIN"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Build Login API"],
        )

    def test_search_matches_description(self):
        response = self.client.get(
            self.url,
            {"search": "coverage"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Write Backend Tests"],
        )

    def test_search_trims_whitespace(self):
        response = self.client.get(
            self.url,
            {"search": "  backend  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Write Backend Tests"],
        )

    def test_empty_search_returns_all_tasks(self):
        response = self.client.get(
            self.url,
            {"search": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)

    def test_search_too_long_returns_400(self):
        response = self.client.get(
            self.url,
            {"search": "x" * 201},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("search", response.data)

    def test_ordering_by_title_ascending(self):
        response = self.client.get(
            self.url,
            {"ordering": "title"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            [
                "Build Login API",
                "Update Documentation",
                "Write Backend Tests",
            ],
        )

    def test_ordering_by_title_descending(self):
        response = self.client.get(
            self.url,
            {"ordering": "-title"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            [
                "Write Backend Tests",
                "Update Documentation",
                "Build Login API",
            ],
        )

    def test_ordering_by_due_date(self):
        response = self.client.get(
            self.url,
            {"ordering": "due_date"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            [
                "Write Backend Tests",
                "Update Documentation",
                "Build Login API",
            ],
        )

    def test_invalid_ordering_returns_400(self):
        response = self.client.get(
            self.url,
            {"ordering": "assignee__email"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ordering", response.data)

    def test_search_filter_and_ordering_together(self):
        response = self.client.get(
            self.url,
            {
                "search": "API",
                "status": "todo",
                "ordering": "title",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            ["Build Login API"],
        )

    def test_unauthorized_user_cannot_use_filters(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(
            self.url,
            {"status": "todo"},
        )

        self.assertEqual(response.status_code, 404)
