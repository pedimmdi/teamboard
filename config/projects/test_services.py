from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import PermissionDenied, ValidationError

from projects.access import get_project_membership_or_404
from projects.models import Project, ProjectMembership
from projects.services import (
    create_project,
    add_project_member,
    change_project_member_role,
    remove_project_member,
)
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ProjectServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password="Strong-password-2026!",
        )
        self.workspace = Workspace.objects.create(name="TeamBoard")

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

    def test_creator_automatically_becomes_manager(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        membership = ProjectMembership.objects.get(
            project=project,
            user=self.owner,
        )
        self.assertEqual(
            membership.role,
            ProjectMembership.Role.MANAGER,
        )

    def test_outsider_cannot_create_project(self):
        with self.assertRaises(PermissionDenied):
            create_project(
                workspace=self.workspace,
                created_by=self.outsider,
                name="Private Project",
            )

        self.assertFalse(
            Project.objects.filter(name="Private Project").exists()
        )

    def test_duplicate_name_is_rejected(self):
        create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(ValidationError):
            create_project(
                workspace=self.workspace,
                created_by=self.owner,
                name="design project",
            )

    def test_name_is_trimmed(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="  Design Project  ",
        )
        self.assertEqual(project.name, "Design Project")

    def test_workspace_member_can_be_added(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        self.assertEqual(
            membership.role,
            ProjectMembership.Role.MEMBER,
        )

    def test_outsider_cannot_be_added(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(ValidationError):
            add_project_member(
                project=project,
                actor=self.owner,
                user=self.outsider,
            )

    def test_duplicate_member_is_rejected(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        with self.assertRaises(ValidationError):
            add_project_member(
                project=project,
                actor=self.owner,
                user=self.member,
            )

    def test_non_member_cannot_access_project(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(Http404):
            get_project_membership_or_404(
                project_id=project.id,
                user=self.member,
            )

    def test_member_cannot_access_manager_action(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        with self.assertRaises(PermissionDenied):
            get_project_membership_or_404(
                project_id=project.id,
                user=self.member,
                roles={ProjectMembership.Role.MANAGER},
            )

    def test_losing_workspace_membership_revokes_access(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        with self.assertRaises(Http404):
            get_project_membership_or_404(
                project_id=project.id,
                user=self.member,
            )

    def test_regular_workspace_member_cannot_create_project(self):
        with self.assertRaises(PermissionDenied):
            create_project(
                workspace=self.workspace,
                created_by=self.member,
                name="Unauthorized Project",
            )


    def test_workspace_owner_can_promote_project_member(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        updated = change_project_member_role(
            project=project,
            actor=self.owner,
            membership_id=membership.pk,
            role=ProjectMembership.Role.MANAGER,
        )

        self.assertEqual(
            updated.role,
            ProjectMembership.Role.MANAGER,
        )


    def test_last_manager_cannot_be_demoted(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        membership = ProjectMembership.objects.get(
            project=project,
            user=self.owner,
        )

        with self.assertRaises(ValidationError):
            change_project_member_role(
                project=project,
                actor=self.owner,
                membership_id=membership.pk,
                role=ProjectMembership.Role.MEMBER,
            )


    def test_manager_can_remove_regular_member(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        remove_project_member(
            project=project,
            actor=self.owner,
            membership_id=membership.pk,
        )

        self.assertFalse(
            ProjectMembership.objects.filter(
                pk=membership.pk,
            ).exists()
        )


    def test_workspace_removal_cleans_project_memberships(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )
        membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        self.assertFalse(
            ProjectMembership.objects.filter(
                pk=membership.pk,
            ).exists()
        )


    def test_last_manager_cannot_leave_workspace(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                WorkspaceMembership.objects.filter(
                    workspace=self.workspace,
                    user=self.owner,
                ).delete()

        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.owner,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )


    def test_manager_can_leave_when_replacement_exists(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        member_membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        change_project_member_role(
            project=project,
            actor=self.owner,
            membership_id=member_membership.pk,
            role=ProjectMembership.Role.MANAGER,
        )

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.owner,
        ).delete()

        self.assertFalse(
            ProjectMembership.objects.filter(
                project=project,
                user=self.owner,
            ).exists()
        )

        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.member,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )


    def test_workspace_deletion_removes_its_projects(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        self.workspace.delete()

        self.assertFalse(
            Project.objects.filter(pk=project.pk).exists()
        )


    def test_bulk_workspace_membership_removal_is_blocked_for_last_manager(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                WorkspaceMembership.objects.filter(
                    workspace=self.workspace,
                    user=self.owner,
                ).delete()

        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.owner,
            ).exists()
        )


    def test_deleting_last_manager_account_is_blocked(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.owner.delete()

        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.owner,
            ).exists()
        )


    def test_removed_member_does_not_regain_access_after_rejoining(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        with self.assertRaises(Http404):
            get_project_membership_or_404(
                project_id=project.pk,
                user=self.member,
            )


    def test_deleting_non_owner_last_manager_is_blocked(self):
        project = create_project(
            workspace=self.workspace,
            created_by=self.owner,
            name="Design Project",
        )

        membership = add_project_member(
            project=project,
            actor=self.owner,
            user=self.member,
        )

        change_project_member_role(
            project=project,
            actor=self.owner,
            membership_id=membership.pk,
            role=ProjectMembership.Role.MANAGER,
        )

        owner_project_membership = ProjectMembership.objects.get(
            project=project,
            user=self.owner,
        )

        change_project_member_role(
            project=project,
            actor=self.owner,
            membership_id=owner_project_membership.pk,
            role=ProjectMembership.Role.MEMBER,
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.member.delete()

        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.member,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )
