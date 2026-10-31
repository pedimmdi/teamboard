from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from projects.models import ProjectMembership
from projects.services import create_project
from workspaces.models import Workspace, WorkspaceMembership


class ProjectValidationTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="validation-owner@example.com")
        self.member = get_user_model().objects.create_user(email="validation-member@example.com")
        self.outsider = get_user_model().objects.create_user(email="validation-outsider@example.com")
        self.workspace = Workspace.objects.create(name="Validation")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.owner, role="owner")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.member)
        self.project = create_project(workspace=self.workspace, created_by=self.owner, name="Project")
        self.membership = ProjectMembership.objects.create(project=self.project, user=self.member)
        self.base = f"/api/v1/workspaces/{self.workspace.slug}/projects/"

    def test_description_limit_on_create_and_update(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.base, {"name": "Too long", "description": "x" * 5001}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"{self.base}{self.project.pk}/", {"description": "x" * 5001}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"{self.base}{self.project.pk}/", {"description": "x" * 5000}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_patch_authorizes_before_validating(self):
        for user, expected in ((self.outsider, 404), (self.member, 403)):
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.patch(f"{self.base}{self.project.pk}/", {"name": ""}, format="json")
                self.assertEqual(response.status_code, expected)

    def test_role_update_authorizes_before_validating(self):
        self.client.force_authenticate(self.member)
        response = self.client.patch(
            f"{self.base}{self.project.pk}/members/{self.membership.pk}/role/",
            {"role": "invalid"}, format="json",
        )
        self.assertEqual(response.status_code, 403)
