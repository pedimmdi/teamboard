from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections, transaction
from django.test import TransactionTestCase

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


class MembershipIntegrityTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="integrity-owner@example.com")
        self.member = get_user_model().objects.create_user(email="integrity-member@example.com")
        self.outsider = get_user_model().objects.create_user(email="integrity-outsider@example.com")
        self.workspace = Workspace.objects.create(name="Integrity")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.owner, role="owner")
        self.workspace_member = WorkspaceMembership.objects.create(workspace=self.workspace, user=self.member)
        with transaction.atomic():
            self.project = Project.objects.create(workspace=self.workspace, name="Project")
            self.manager = ProjectMembership.objects.create(project=self.project, user=self.owner, role="manager")

    def test_direct_insert_requires_workspace_membership(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMembership.objects.create(project=self.project, user=self.outsider)

    def test_raw_workspace_delete_cannot_leave_stale_project_membership(self):
        ProjectMembership.objects.create(project=self.project, user=self.member)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute("DELETE FROM workspaces_workspacemembership WHERE id = %s", [self.workspace_member.pk])

    def test_raw_workspace_user_update_cannot_orphan_project_member(self):
        ProjectMembership.objects.create(project=self.project, user=self.member)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceMembership.objects.filter(pk=self.workspace_member.pk).update(user=self.outsider)

    def test_invalid_roles_are_rejected_by_database(self):
        for queryset in (
            ProjectMembership.objects.filter(pk=self.manager.pk),
            WorkspaceMembership.objects.filter(pk=self.workspace_member.pk),
        ):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    queryset.update(role="invalid")

    def race(self, first, second):
        barrier = Barrier(2)

        def run(operation):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '10s'")
                    operation()
                return "committed"
            except IntegrityError:
                return "blocked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run, operation) for operation in (first, second)]
            return [future.result(timeout=25) for future in futures]

    def test_concurrent_demotions_preserve_manager(self):
        second = ProjectMembership.objects.create(project=self.project, user=self.member, role="manager")
        results = self.race(
            lambda: ProjectMembership.objects.filter(pk=self.manager.pk).update(role="member"),
            lambda: ProjectMembership.objects.filter(pk=second.pk).update(role="member"),
        )
        self.assertCountEqual(results, ["committed", "blocked"])
        self.assertEqual(ProjectMembership.objects.filter(project=self.project, role="manager").count(), 1)

    def test_concurrent_join_and_workspace_departure_never_leave_orphan(self):
        self.race(
            lambda: ProjectMembership.objects.create(project=self.project, user=self.member),
            lambda: WorkspaceMembership.objects.filter(pk=self.workspace_member.pk).delete(),
        )
        if ProjectMembership.objects.filter(project=self.project, user=self.member).exists():
            self.assertTrue(WorkspaceMembership.objects.filter(workspace=self.workspace, user=self.member).exists())

    def test_concurrent_demotion_and_workspace_departure_preserve_manager(self):
        ProjectMembership.objects.create(project=self.project, user=self.member, role="manager")
        def leave():
            # Raw SQL bypasses Django's pre-delete guard, exercising the database.
            with connections["default"].cursor() as cursor:
                cursor.execute("DELETE FROM projects_projectmembership WHERE project_id = %s AND user_id = %s", [self.project.pk, self.member.pk])
                cursor.execute("DELETE FROM workspaces_workspacemembership WHERE id = %s", [self.workspace_member.pk])

        self.assertCountEqual(self.race(
            lambda: ProjectMembership.objects.filter(pk=self.manager.pk).update(role="member"), leave,
        ), ["committed", "blocked"])
        self.assertEqual(ProjectMembership.objects.filter(project=self.project, role="manager").count(), 1)

    def test_api_race_between_manager_demotion_and_workspace_leave(self):
        from rest_framework.test import APIClient

        ProjectMembership.objects.create(project=self.project, user=self.member, role="manager")
        barrier = Barrier(2)

        def request(user, path, body=None):
            connections.close_all()
            try:
                client = APIClient()
                client.force_authenticate(user)
                barrier.wait(timeout=10)
                if body is None:
                    return client.post(path).status_code
                return client.patch(path, body, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            demote = executor.submit(request, self.owner,
                f"/api/v1/workspaces/{self.workspace.slug}/projects/{self.project.pk}/members/{self.manager.pk}/role/",
                {"role": "member"})
            leave = executor.submit(request, self.member, f"/api/v1/workspaces/{self.workspace.slug}/leave/")
            results = [demote.result(timeout=25), leave.result(timeout=25)]
        self.assertTrue(any(code in {200, 204} for code in results))
        self.assertTrue(all(code in {200, 204, 400, 409} for code in results), results)
        self.assertTrue(ProjectMembership.objects.filter(project=self.project, role="manager").exists())
