from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


class AdminDeletionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(email="delete-admin@example.com", password="Admin-test-2026!")
        self.owner = get_user_model().objects.create_user(email="delete-owner@example.com")
        self.manager = get_user_model().objects.create_user(email="delete-manager@example.com")
        self.workspace = Workspace.objects.create(name="Protected workspace")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.owner, role="owner")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.manager)
        self.project = Project.objects.create(workspace=self.workspace, name="Protected project")
        ProjectMembership.objects.create(project=self.project, user=self.manager, role="manager")
        self.client.force_login(self.admin)

    def test_owner_single_deletion_shows_protection_instead_of_server_error(self):
        url = reverse("admin:accounts_user_delete", args=[self.owner.pk])
        self.assertContains(self.client.get(url), "Transfer workspace ownership")
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=self.owner.pk).exists())

    def test_last_manager_single_deletion_shows_protection(self):
        url = reverse("admin:accounts_user_delete", args=[self.manager.pk])
        self.assertContains(self.client.get(url), "Assign another manager")
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=self.manager.pk).exists())

    def test_bulk_deletion_protects_owners(self):
        url = reverse("admin:accounts_user_changelist")
        response = self.client.post(url, {"action": "delete_selected", "_selected_action": [self.owner.pk], "post": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(pk=self.owner.pk).exists())

    def test_bulk_deletion_cannot_remove_all_managers_together(self):
        other = get_user_model().objects.create_user(email="delete-second-manager@example.com")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=other)
        ProjectMembership.objects.create(project=self.project, user=other, role="manager")
        response = self.client.post(reverse("admin:accounts_user_changelist"), {
            "action": "delete_selected", "_selected_action": [self.manager.pk, other.pk], "post": "yes",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProjectMembership.objects.filter(project=self.project, role="manager").count(), 2)

    def test_unprotected_user_can_still_be_deleted(self):
        disposable = get_user_model().objects.create_user(email="delete-disposable@example.com")
        response = self.client.post(reverse("admin:accounts_user_delete", args=[disposable.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=disposable.pk).exists())

    def test_race_after_confirmation_returns_message_instead_of_server_error(self):
        disposable = get_user_model().objects.create_user(email="delete-race@example.com")
        with patch("accounts.admin.UserAdmin.delete_model", side_effect=ProtectedError("Transfer ownership first.", [])):
            response = self.client.post(reverse("admin:accounts_user_delete", args=[disposable.pk]), {"post": "yes"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transfer ownership first.")
        self.assertTrue(get_user_model().objects.filter(pk=disposable.pk).exists())
