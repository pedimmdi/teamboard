
from django.test import TestCase
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
