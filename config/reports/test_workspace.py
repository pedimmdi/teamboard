
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


class WorkspaceReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="workspace-report-owner@example.com",
            password="Test-password-123!",
        )
        cls.member = User.objects.create_user(
            email="workspace-report-member@example.com",
            password="Test-password-123!",
        )
        cls.outsider = User.objects.create_user(
            email="workspace-report-outsider@example.com",
            password="Test-password-123!",
        )

        cls.workspace = Workspace.objects.create(
            name="Analytics Workspace",
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

        cls.visible_project = Project.objects.create(
            workspace=cls.workspace,
            name="Visible Project",
            created_by=cls.owner,
        )
        cls.private_project = Project.objects.create(
            workspace=cls.workspace,
            name="Private Project",
            created_by=cls.owner,
        )

        for project in (
            cls.visible_project,
            cls.private_project,
        ):
            ProjectMembership.objects.create(
                project=project,
                user=cls.owner,
                role=ProjectMembership.Role.MANAGER,
            )

        ProjectMembership.objects.create(
            project=cls.visible_project,
            user=cls.member,
            role=ProjectMembership.Role.MEMBER,
        )

        Task.objects.create(
            project=cls.visible_project,
            title="Visible task",
            status=Task.Status.DONE,
        )
        Task.objects.create(
            project=cls.private_project,
            title="Private task",
            status=Task.Status.TODO,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = reverse(
            "workspaces_api_v1:reports_api_v1:workspace-report",
            kwargs={"slug": self.workspace.slug},
        )

    def test_owner_sees_all_projects(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_projects"], 2)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 2
        )
        self.assertEqual(
            response.data["summary"]["completion_rate"], 50.0
        )

    def test_member_sees_only_accessible_projects(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_projects"], 1)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 1
        )
        self.assertEqual(
            response.data["summary"]["completion_rate"], 100.0
        )
        self.assertEqual(
            response.data["projects"][0]["project_name"],
            "Visible Project",
        )

    def test_outsider_cannot_access_workspace_report(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_access_workspace_report(self):
        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))

    def test_workspace_report_is_read_only(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 405)

    def test_workspace_admin_sees_all_projects(self):
        admin = User.objects.create_user(
            email="workspace-report-admin@example.com",
            password="Test-password-123!",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=admin,
            role=WorkspaceMembership.Role.ADMIN,
        )

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_projects"], 2)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 2
        )

    def test_member_without_project_membership_sees_empty_report(self):
        member = User.objects.create_user(
            email="no-project-report@example.com",
            password="Test-password-123!",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=member)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_projects"], 0)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 0
        )
        self.assertEqual(response.data["projects"], [])

    def test_other_workspace_tasks_are_not_counted(self):
        other_workspace = Workspace.objects.create(
            name="Isolated Reports Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=other_workspace,
            user=self.outsider,
            role=WorkspaceMembership.Role.OWNER,
        )

        other_project = Project.objects.create(
            workspace=other_workspace,
            name="Isolated Project",
            created_by=self.outsider,
        )

        ProjectMembership.objects.create(
            project=other_project,
            user=self.outsider,
            role=ProjectMembership.Role.MANAGER,
        )

        Task.objects.create(
            project=other_project,
            title="Isolated task",
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_projects"], 2)
        self.assertEqual(
            response.data["summary"]["total_tasks"], 2
        )
