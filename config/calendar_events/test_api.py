from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


class ProjectCalendarTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(email="calendar-owner@example.com")
        cls.member = user_model.objects.create_user(email="calendar-member@example.com")
        cls.workspace = Workspace.objects.create(name="Calendar")
        WorkspaceMembership.objects.create(workspace=cls.workspace, user=cls.owner, role="owner")
        WorkspaceMembership.objects.create(workspace=cls.workspace, user=cls.member, role="member")
        cls.project = Project.objects.create(
            name="Launch", workspace=cls.workspace, created_by=cls.owner,
        )
        ProjectMembership.objects.create(project=cls.project, user=cls.owner, role="manager")
        cls.assigned = Task.objects.create(
            project=cls.project, title="First day", assignee=cls.owner, due_date=date(2026, 1, 1),
        )
        cls.unassigned = Task.objects.create(
            project=cls.project, title="Last day", due_date=date(2026, 1, 31),
        )
        Task.objects.create(project=cls.project, title="Undated")
        Task.objects.create(project=cls.project, title="Outside", due_date=date(2026, 2, 1))

    def setUp(self):
        self.url = reverse("workspaces_api_v1:calendar_events_api_v1:project-tasks", kwargs={
            "slug": self.workspace.slug, "project_id": self.project.pk,
        })
        self.range = {"start": "2026-01-01", "end": "2026-01-31"}
        self.client.force_authenticate(self.owner)

    def test_range_is_inclusive_ordered_and_paginated(self):
        response = self.client.get(self.url, {**self.range, "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        result = response.data["results"][0]
        self.assertEqual(result["id"], str(self.assigned.pk))
        self.assertEqual(result["project_name"], self.project.name)
        self.assertEqual(result["assignee_email"], self.owner.email)
        response = self.client.get(response.data["next"])
        self.assertEqual(response.data["results"][0]["id"], str(self.unassigned.pk))

    def test_assignee_filters(self):
        for assignee, task in (
            ("me", self.assigned), (str(self.owner.pk), self.assigned),
            ("unassigned", self.unassigned),
        ):
            with self.subTest(assignee=assignee):
                response = self.client.get(self.url, {**self.range, "assignee": assignee})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["id"] for row in response.data["results"]], [str(task.pk)])

    def test_invalid_query_and_permissions(self):
        for query in (
            {}, {**self.range, "end": "2025-01-01"},
            {**self.range, "start": "invalid"}, {**self.range, "assignee": "invalid"},
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.url, query).status_code, 400)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        ProjectMembership.objects.create(project=self.project, user=self.member, role="member")
        self.assertEqual(self.client.get(self.url, self.range).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url, self.range).status_code, 401)
