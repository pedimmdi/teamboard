from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


class WorkspaceProjectAccessTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(email="global-owner@example.com")
        self.admin = users.create_user(email="global-admin@example.com")
        self.manager = users.create_user(email="global-manager@example.com")
        self.target = users.create_user(email="global-target@example.com")
        self.outsider = users.create_user(email="global-outsider@example.com")
        self.workspace = Workspace.objects.create(name="Global access")
        for user, role in ((self.owner, "owner"), (self.admin, "admin"), (self.manager, "member"), (self.target, "member")):
            WorkspaceMembership.objects.create(workspace=self.workspace, user=user, role=role)

    def project(self, name="Project"):
        project = Project.objects.create(workspace=self.workspace, name=name)
        ProjectMembership.objects.create(project=project, user=self.manager, role="manager")
        return project

    def base(self, project):
        return f"/api/v1/workspaces/{self.workspace.slug}/projects/{project.pk}/"

    def test_privileged_users_manage_without_project_membership(self):
        for actor in (self.owner, self.admin):
            with self.subTest(actor=actor.email):
                project = self.project(actor.email)
                base = self.base(project)
                self.client.force_authenticate(actor)
                response = self.client.get(f"/api/v1/workspaces/{self.workspace.slug}/projects/")
                self.assertIn(str(project.pk), [str(row["id"]) for row in response.data["results"]])
                self.assertEqual(self.client.get(base).status_code, 200)
                self.assertEqual(self.client.get(base + "members/").status_code, 200)
                self.assertEqual(self.client.patch(base, {"description": "Updated"}, format="json").status_code, 200)
                response = self.client.post(base + "members/", {"user_id": self.target.pk}, format="json")
                self.assertEqual(response.status_code, 201)
                member_id = response.data["id"]
                response = self.client.patch(base + f"members/{member_id}/role/", {"role": "manager"}, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.delete(base + f"members/{member_id}/").status_code, 204)
                self.assertFalse(ProjectMembership.objects.filter(project=project, user=actor).exists())
                self.assertEqual(self.client.delete(base).status_code, 204)

    def test_workspace_role_does_not_cross_workspace_boundary(self):
        project = self.project()
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.base(project)).status_code, 404)
        self.client.force_authenticate(self.target)
        self.assertEqual(self.client.get(self.base(project)).status_code, 404)

    def test_privilege_downgrade_revokes_implicit_access(self):
        project = self.project()
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.base(project)).status_code, 200)
        WorkspaceMembership.objects.filter(workspace=self.workspace, user=self.admin).update(role="member")
        self.assertEqual(self.client.get(self.base(project)).status_code, 404)

    def test_workspace_admin_with_member_project_role_can_still_manage(self):
        project = self.project()
        ProjectMembership.objects.create(project=project, user=self.admin, role="member")
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.base(project), {"description": "Managed"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProjectMembership.objects.get(project=project, user=self.admin).role, "member")

    def test_regular_project_manager_cannot_remove_other_managers(self):
        project = self.project()
        target = ProjectMembership.objects.create(project=project, user=self.target, role="manager")
        self.client.force_authenticate(self.manager)
        response = self.client.delete(self.base(project) + f"members/{target.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_last_manager_workspace_leave_and_removal_return_conflict(self):
        project = self.project()
        membership = WorkspaceMembership.objects.get(workspace=self.workspace, user=self.manager)
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f"/api/v1/workspaces/{self.workspace.slug}/members/{membership.pk}/")
        self.assertEqual(response.status_code, 409)
        message = "Assign another manager before removing this user from the workspace."
        self.assertEqual(response.data["detail"], message)
        self.client.force_authenticate(self.manager)
        response = self.client.post(f"/api/v1/workspaces/{self.workspace.slug}/leave/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], message)
        self.assertTrue(WorkspaceMembership.objects.filter(pk=membership.pk).exists())
        # The workspace owner can resolve the conflict without joining the project.
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.base(project) + "members/", {"user_id": self.target.pk, "role": "manager"}, format="json")
        self.assertEqual(response.status_code, 201)
        response = self.client.delete(f"/api/v1/workspaces/{self.workspace.slug}/members/{membership.pk}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ProjectMembership.objects.filter(project=project, user=self.manager).exists())
