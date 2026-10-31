
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ProjectModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="Strong-password-2026!",
        )
        self.workspace = Workspace.objects.create(
            name="TeamBoard",
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

    def create_project_with_manager(self, *, workspace=None, **kwargs):
        workspace = workspace or self.workspace

        project = Project.objects.create(
            workspace=workspace,
            **kwargs,
        )

        WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=self.user,
            defaults={"role": WorkspaceMembership.Role.MEMBER},
        )

        ProjectMembership.objects.create(
            project=project,
            user=self.user,
            role=ProjectMembership.Role.MANAGER,
        )

        return project

    def test_create_project(self):
        project = self.create_project_with_manager(
            workspace=self.workspace,
            name="Website Redesign",
            description="Redesign the website",
            created_by=self.user,
        )

        self.assertEqual(project.workspace, self.workspace)
        self.assertEqual(project.created_by, self.user)
        self.assertEqual(str(project), "Website Redesign")

    def test_project_names_can_repeat_across_workspaces(self):
        other_workspace = Workspace.objects.create(
            name="Second Workspace",
        )

        first = self.create_project_with_manager(
            workspace=self.workspace,
            name="Design Project",
            created_by=self.user,
        )
        second = self.create_project_with_manager(
            workspace=other_workspace,
            name="Design Project",
            created_by=self.user,
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(first.workspace_id, second.workspace_id)

    def test_duplicate_project_name_in_same_workspace_is_blocked(self):
        self.create_project_with_manager(
            workspace=self.workspace,
            name="Design Project",
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.create(
                    workspace=self.workspace,
                    name="design project",
                    created_by=self.user,
                )

    def test_duplicate_project_membership_is_blocked(self):
        project = self.create_project_with_manager(
            workspace=self.workspace,
            name="Website",
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.create(
                    project=project,
                    user=self.user,
                )

    def test_deleting_workspace_deletes_projects(self):
        project = self.create_project_with_manager(
            workspace=self.workspace,
            name="Website",
            created_by=self.user,
        )

        self.workspace.delete()

        self.assertFalse(
            Project.objects.filter(pk=project.pk).exists()
        )
        self.assertFalse(
            ProjectMembership.objects.filter(
                project_id=project.pk
            ).exists()
        )

    def test_deleting_creator_preserves_project(self):
        project = self.create_project_with_manager(
            workspace=self.workspace,
            name="Website",
            created_by=self.user,
        )

        # Create a separate creator so the workspace
        # owner protection does not block deletion.
        creator = User.objects.create_user(
            email="creator@example.com",
            password="Strong-password-2026!",
        )
        project.created_by = creator
        project.save(update_fields=["created_by"])

        creator.delete()
        project.refresh_from_db()

        self.assertIsNone(project.created_by)
