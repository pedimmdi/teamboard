from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from projects.services import create_project
from workspaces.models import Workspace, WorkspaceMembership


class ResourceAvatarTests(APITestCase):
    def test_workspace_and_project_images_follow_edit_permissions_and_cleanup(self):
        User = get_user_model()
        owner = User.objects.create_user(email="resource-owner@example.com")
        member = User.objects.create_user(email="resource-member@example.com")
        workspace = Workspace.objects.create(name="Avatar workspace")
        WorkspaceMembership.objects.create(workspace=workspace, user=owner, role="owner")
        WorkspaceMembership.objects.create(workspace=workspace, user=member, role="member")
        project = create_project(workspace=workspace, created_by=owner, name="Avatar project")
        project.memberships.create(user=member, role="member")
        base = f"/api/v1/workspaces/{workspace.slug}/"
        buffer = BytesIO()
        Image.new("RGB", (24, 24), "blue").save(buffer, format="PNG")

        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            for resource, url in ((workspace, base), (project, f"{base}projects/{project.pk}/")):
                with self.subTest(resource=type(resource).__name__):
                    self.client.force_authenticate(member)
                    self.assertEqual(self.client.patch(url, {"avatar": None}, format="json").status_code, 403)
                    self.client.force_authenticate(owner)
                    response = self.client.patch(url, {
                        "avatar": SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png"),
                    }, format="multipart")
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertIn("/media/", response.data["avatar"])
                    resource.refresh_from_db()
                    filename = resource.avatar.name
                    self.assertTrue(resource.avatar.storage.exists(filename))
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.client.patch(url, {"avatar": None}, format="json")
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertIsNone(response.data["avatar"])
                    self.assertFalse(resource.avatar.storage.exists(filename))
