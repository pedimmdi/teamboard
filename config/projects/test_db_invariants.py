from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections, transaction
from django.test import TransactionTestCase

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ProjectDatabaseInvariantTests(TransactionTestCase):
    def test_direct_orm_delete_of_last_manager_is_blocked(self):
        user = User.objects.create_user(
            email="db-manager@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Database Safety Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Protected Project",
                created_by=user,
            )

            membership = ProjectMembership.objects.create(
                project=project,
                user=user,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.filter(
                    pk=membership.pk,
                ).delete()

        self.assertTrue(
            ProjectMembership.objects.filter(
                pk=membership.pk,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )

    def test_cannot_move_project_to_another_workspace(self):
        owner = User.objects.create_user(
            email="project-transfer-owner@example.com",
            password="StrongTestPassword123!",
        )

        first_workspace = Workspace.objects.create(
            name="First Workspace",
        )
        second_workspace = Workspace.objects.create(
            name="Second Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=first_workspace,
            user=owner,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=first_workspace,
                name="Protected Project",
                created_by=owner,
            )
            ProjectMembership.objects.create(
                project=project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.filter(pk=project.pk).update(
                    workspace=second_workspace,
                )

        project.refresh_from_db()
        self.assertEqual(project.workspace_id, first_workspace.pk)

    def test_cannot_move_membership_to_another_project(self):
        owner = User.objects.create_user(
            email="membership-transfer-owner@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Membership Safety Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=owner,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            first_project = Project.objects.create(
                workspace=workspace,
                name="First Project",
                created_by=owner,
            )
            first_membership = ProjectMembership.objects.create(
                project=first_project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

            second_project = Project.objects.create(
                workspace=workspace,
                name="Second Project",
                created_by=owner,
            )
            ProjectMembership.objects.create(
                project=second_project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.filter(
                    pk=first_membership.pk,
                ).update(project=second_project)

        first_membership.refresh_from_db()
        self.assertEqual(
            first_membership.project_id,
            first_project.pk,
        )

    def test_concurrent_manager_deletions_preserve_one_manager(self):
        first_user = User.objects.create_user(
            email="concurrent-first@example.com",
            password="StrongTestPassword123!",
        )
        second_user = User.objects.create_user(
            email="concurrent-second@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Concurrent Safety Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=first_user,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=second_user,
            role=WorkspaceMembership.Role.MEMBER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Concurrent Project",
                created_by=first_user,
            )

            first_membership = ProjectMembership.objects.create(
                project=project,
                user=first_user,
                role=ProjectMembership.Role.MANAGER,
            )
            second_membership = ProjectMembership.objects.create(
                project=project,
                user=second_user,
                role=ProjectMembership.Role.MANAGER,
            )

        barrier = Barrier(2)

        def delete_manager(membership_id):
            connections.close_all()

            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    ProjectMembership.objects.filter(
                        pk=membership_id,
                    ).delete()

                return "deleted"

            except IntegrityError:
                return "blocked"

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                delete_manager,
                first_membership.pk,
            )
            second_future = executor.submit(
                delete_manager,
                second_membership.pk,
            )

            results = [
                first_future.result(timeout=30),
                second_future.result(timeout=30),
            ]

        remaining_managers = ProjectMembership.objects.filter(
            project=project,
            role=ProjectMembership.Role.MANAGER,
        ).count()

        self.assertEqual(remaining_managers, 1)
        self.assertCountEqual(results, ["deleted", "blocked"])

    def test_direct_orm_demotion_of_last_manager_is_blocked(self):
        owner = User.objects.create_user(
            email="demotion-owner@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Demotion Safety Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=owner,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Demotion Protected Project",
                created_by=owner,
            )
            membership = ProjectMembership.objects.create(
                project=project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.filter(
                    pk=membership.pk,
                ).update(
                    role=ProjectMembership.Role.MEMBER,
                )

        membership.refresh_from_db()
        self.assertEqual(
            membership.role,
            ProjectMembership.Role.MANAGER,
        )

    def test_removing_last_manager_from_workspace_is_blocked(self):
        from django.db.models.deletion import ProtectedError

        owner = User.objects.create_user(
            email="workspace-safety-owner@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Workspace Membership Safety",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=owner,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Workspace Protected Project",
                created_by=owner,
            )
            ProjectMembership.objects.create(
                project=project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                WorkspaceMembership.objects.filter(
                    workspace=workspace,
                    user=owner,
                ).delete()

        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=owner,
            ).exists()
        )
        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )

    def test_cannot_transfer_membership_to_another_user(self):
        owner = User.objects.create_user(
            email="immutable-owner@example.com",
            password="StrongTestPassword123!",
        )
        other_user = User.objects.create_user(
            email="immutable-other@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Immutable Membership Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=owner,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=other_user,
            role=WorkspaceMembership.Role.MEMBER,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Immutable Membership Project",
                created_by=owner,
            )
            membership = ProjectMembership.objects.create(
                project=project,
                user=owner,
                role=ProjectMembership.Role.MANAGER,
            )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.filter(
                    pk=membership.pk,
                ).update(user=other_user)

        membership.refresh_from_db()
        self.assertEqual(membership.user_id, owner.pk)

    def test_manager_can_leave_workspace_after_replacement(self):
        first_user = User.objects.create_user(
            email="replacement-first@example.com",
            password="StrongTestPassword123!",
        )
        second_user = User.objects.create_user(
            email="replacement-second@example.com",
            password="StrongTestPassword123!",
        )

        workspace = Workspace.objects.create(
            name="Replacement Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=first_user,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=second_user,
            role=WorkspaceMembership.Role.ADMIN,
        )

        with transaction.atomic():
            project = Project.objects.create(
                workspace=workspace,
                name="Replacement Project",
                created_by=first_user,
            )
            ProjectMembership.objects.create(
                project=project,
                user=first_user,
                role=ProjectMembership.Role.MANAGER,
            )
            ProjectMembership.objects.create(
                project=project,
                user=second_user,
                role=ProjectMembership.Role.MANAGER,
            )

        with transaction.atomic():
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=second_user,
            ).delete()

        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=second_user,
            ).exists()
        )
        self.assertFalse(
            ProjectMembership.objects.filter(
                project=project,
                user=second_user,
            ).exists()
        )
        self.assertEqual(
            ProjectMembership.objects.filter(
                project=project,
                role=ProjectMembership.Role.MANAGER,
            ).count(),
            1,
        )
