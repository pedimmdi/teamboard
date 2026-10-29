from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from workspaces.services import hash_invitation_token


User = get_user_model()


class WorkspaceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="Strong-password-2026!",
        )

    def test_workspace_slug_has_ten_characters(self):
        workspace = Workspace.objects.create(
            name="TeamBoard",
        )

        self.assertEqual(len(workspace.slug), 10)
        self.assertRegex(workspace.slug, r"^[a-z0-9]{10}$")

    def test_workspace_names_can_be_duplicated(self):
        first = Workspace.objects.create(name="TeamBoard")
        second = Workspace.objects.create(name="TeamBoard")

        self.assertEqual(first.name, second.name)
        self.assertNotEqual(first.slug, second.slug)

    def test_user_can_have_only_one_membership_per_workspace(self):
        workspace = Workspace.objects.create(name="TeamBoard")

        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceMembership.objects.create(
                    workspace=workspace,
                    user=self.user,
                    role=WorkspaceMembership.Role.MEMBER,
                )

    def test_deleting_workspace_owner_is_blocked(self):
        workspace = Workspace.objects.create(
            name="Owned Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.user.delete()

        self.assertTrue(
            User.objects.filter(pk=self.user.pk).exists()
        )
        self.assertTrue(
            Workspace.objects.filter(pk=workspace.pk).exists()
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.user,
                role=WorkspaceMembership.Role.OWNER,
            ).exists()
        )

    def test_deleting_non_owner_user_preserves_workspace_owner(self):
        workspace = Workspace.objects.create(
            name="Shared Workspace",
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        member = User.objects.create_user(
            email="member-to-delete@example.com",
            password="Strong-password-2026!",
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        member_id = member.pk
        member.delete()

        self.assertFalse(
            User.objects.filter(pk=member.pk).exists()
        )
        self.assertTrue(
            Workspace.objects.filter(pk=workspace.pk).exists()
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user=self.user,
                role=WorkspaceMembership.Role.OWNER,
            ).exists()
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                user_id=member_id,
            ).exists()
        )


class WorkspaceAPITests(APITestCase):
    list_url = "/api/v1/workspaces/"

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

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_workspace(self, user, name="TeamBoard"):
        self.authenticate(user)

        return self.client.post(
            self.list_url,
            {"name": name},
            format="json",
        )

    def test_workspace_creation_assigns_creator_as_owner(self):
        response = self.create_workspace(self.owner)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        workspace = Workspace.objects.get(
            slug=response.data["slug"],
        )
        membership = WorkspaceMembership.objects.get(
            workspace=workspace,
            user=self.owner,
        )

        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)
        self.assertEqual(len(workspace.slug), 10)
        self.assertEqual(
            response.data["role"],
            WorkspaceMembership.Role.OWNER,
        )

    def test_creation_does_not_allow_client_to_choose_slug_or_role(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            {
                "name": "TeamBoard",
                "slug": "customslug",
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        workspace = Workspace.objects.get(
            slug=response.data["slug"],
        )
        membership = WorkspaceMembership.objects.get(
            workspace=workspace,
            user=self.owner,
        )

        self.assertNotEqual(workspace.slug, "customslug")
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)

    def test_unauthenticated_user_cannot_list_workspaces(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unauthenticated_user_cannot_create_workspace(self):
        response = self.client.post(
            self.list_url,
            {"name": "TeamBoard"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(Workspace.objects.count(), 0)

    def test_user_sees_only_workspaces_they_belong_to(self):
        own_response = self.create_workspace(
            self.owner,
            "Owner Workspace",
        )
        self.assertEqual(
            own_response.status_code,
            status.HTTP_201_CREATED,
        )

        other_response = self.create_workspace(
            self.member,
            "Member Workspace",
        )
        self.assertEqual(
            other_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.authenticate(self.owner)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Owner Workspace",
        )
        self.assertEqual(
            response.data["results"][0]["role"],
            WorkspaceMembership.Role.OWNER,
        )

    def test_non_member_cannot_retrieve_workspace(self):
        create_response = self.create_workspace(self.owner)
        slug = create_response.data["slug"]

        self.authenticate(self.outsider)
        response = self.client.get(
            f"{self.list_url}{slug}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_member_can_retrieve_workspace(self):
        create_response = self.create_workspace(self.owner)
        slug = create_response.data["slug"]

        WorkspaceMembership.objects.create(
            workspace=Workspace.objects.get(slug=slug),
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.authenticate(self.member)
        response = self.client.get(
            f"{self.list_url}{slug}/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], slug)
        self.assertEqual(
            response.data["role"],
            WorkspaceMembership.Role.MEMBER,
        )

    def test_creation_rejects_blank_name(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            {"name": "   "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(Workspace.objects.count(), 0)

    def test_workspace_creation_is_throttled(self):
        cache.clear()

        for index in range(5):
            response = self.create_workspace(
                self.owner,
                name=f"TeamBoard {index}",
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )

        response = self.create_workspace(
            self.owner,
            name="TeamBoard over limit",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


class WorkspaceManagementAPITests(APITestCase):
    list_url = "/api/v1/workspaces/"

    def setUp(self):
        self.owner = self.create_user("owner@example.com")
        self.admin = self.create_user("admin@example.com")
        self.member = self.create_user("member@example.com")
        self.other_member = self.create_user("other@example.com")
        self.outsider = self.create_user("outsider@example.com")

        self.workspace = Workspace.objects.create(
            name="TeamBoard",
        )

        self.owner_membership = self.add_member(
            self.owner,
            WorkspaceMembership.Role.OWNER,
        )
        self.admin_membership = self.add_member(
            self.admin,
            WorkspaceMembership.Role.ADMIN,
        )
        self.member_membership = self.add_member(
            self.member,
            WorkspaceMembership.Role.MEMBER,
        )
        self.other_membership = self.add_member(
            self.other_member,
            WorkspaceMembership.Role.MEMBER,
        )

    def create_user(self, email, **extra_fields):
        return User.objects.create_user(
            email=email,
            password="Strong-password-2026!",
            **extra_fields,
        )

    def add_member(self, user, role):
        return WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=user,
            role=role,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def workspace_url(self):
        return f"{self.list_url}{self.workspace.slug}/"

    def members_url(self):
        return f"{self.workspace_url()}members/"

    def membership_url(self, membership):
        return f"{self.members_url()}{membership.id}/"

    def role_url(self, membership):
        return f"{self.membership_url(membership)}role/"

    def leave_url(self):
        return f"{self.workspace_url()}leave/"

    def transfer_url(self):
        return f"{self.workspace_url()}transfer-ownership/"

    def invitations_url(self):
        return f"{self.workspace_url()}invitations/"

    def create_invitation(self, email="invitee@example.com"):
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.invitations_url(),
                {"email": email},
                format="json",
            )

        return response

    def test_owner_can_update_workspace_name(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.workspace_url(),
            {"name": "Updated Team"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, "Updated Team")

    def test_patch_nonexistent_workspace_returns_404(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            f"{self.list_url}missing-org-slug/",
            {"name": "Updated Team"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_admin_can_update_workspace_name(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.workspace_url(),
            {"name": "Admin Updated Team"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, "Admin Updated Team")

    def test_member_cannot_update_workspace(self):
        self.authenticate(self.member)

        response = self.client.patch(
            self.workspace_url(),
            {"name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, "TeamBoard")

    def test_outsider_cannot_update_workspace(self):
        self.authenticate(self.outsider)

        response = self.client.patch(
            self.workspace_url(),
            {"name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_rejects_blank_name(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.workspace_url(),
            {"name": "   "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_does_not_allow_changing_slug(self):
        original_slug = self.workspace.slug
        self.authenticate(self.owner)

        response = self.client.patch(
            self.workspace_url(),
            {
                "name": "Updated Team",
                "slug": "customslug",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.slug, original_slug)

    def test_owner_can_delete_workspace_without_deleting_users(self):
        self.authenticate(self.owner)

        response = self.client.delete(self.workspace_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Workspace.objects.filter(pk=self.workspace.pk).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace_id=self.workspace.pk,
            ).exists()
        )

    def test_admin_cannot_delete_workspace(self):
        self.authenticate(self.admin)

        response = self.client.delete(self.workspace_url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            Workspace.objects.filter(pk=self.workspace.pk).exists()
        )

    def test_member_cannot_delete_workspace(self):
        self.authenticate(self.member)

        response = self.client.delete(self.workspace_url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_leave_workspace(self):
        self.authenticate(self.member)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.member,
            ).exists()
        )
        self.assertTrue(
            Workspace.objects.filter(pk=self.workspace.pk).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_admin_can_leave_workspace(self):
        self.authenticate(self.admin)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.admin,
            ).exists()
        )

    def test_owner_cannot_leave_workspace(self):
        self.authenticate(self.owner)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.owner,
                role=WorkspaceMembership.Role.OWNER,
            ).exists()
        )

    def test_non_member_cannot_leave_workspace(self):
        self.authenticate(self.outsider)

        response = self.client.post(self.leave_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_can_view_member_list(self):
        self.authenticate(self.member)

        response = self.client.get(self.members_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(results), 4)

        current_user_rows = [
            row for row in results
            if row["is_current_user"]
        ]
        self.assertEqual(len(current_user_rows), 1)

        current_user_row = current_user_rows[0]
        self.assertEqual(current_user_row["user_id"], self.member.pk)
        self.assertEqual(current_user_row["user_email"], self.member.email)
        self.assertEqual(
            current_user_row["role"],
            WorkspaceMembership.Role.MEMBER,
        )
        self.assertTrue(all("user_id" in row for row in results))

    def test_outsider_cannot_view_member_list(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.members_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_promote_member_to_admin(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.member_membership),
            {"role": WorkspaceMembership.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(
            self.member_membership.role,
            WorkspaceMembership.Role.ADMIN,
        )

    def test_owner_can_demote_admin_to_member(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.admin_membership),
            {"role": WorkspaceMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_membership.refresh_from_db()
        self.assertEqual(
            self.admin_membership.role,
            WorkspaceMembership.Role.MEMBER,
        )

    def test_admin_cannot_change_member_roles(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.role_url(self.member_membership),
            {"role": WorkspaceMembership.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_role_cannot_be_changed_through_role_endpoint(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.owner_membership),
            {"role": WorkspaceMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.owner_membership.refresh_from_db()
        self.assertEqual(
            self.owner_membership.role,
            WorkspaceMembership.Role.OWNER,
        )

    def test_owner_can_remove_member_without_deleting_user(self):
        self.authenticate(self.owner)

        response = self.client.delete(
            self.membership_url(self.member_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                pk=self.member_membership.pk,
            ).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_admin_can_remove_member(self):
        self.authenticate(self.admin)

        response = self.client.delete(
            self.membership_url(self.member_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_admin_cannot_remove_another_admin(self):
        self.other_membership.role = WorkspaceMembership.Role.ADMIN
        self.other_membership.save(update_fields=["role"])

        self.authenticate(self.admin)

        response = self.client.delete(
            self.membership_url(self.other_membership),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                pk=self.other_membership.pk,
            ).exists()
        )

    def test_member_cannot_remove_another_member(self):
        self.authenticate(self.member)

        response = self.client.delete(
            self.membership_url(self.other_membership),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                pk=self.other_membership.pk,
            ).exists()
        )

    def test_owner_can_transfer_ownership(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.transfer_url(),
            {"membership_id": str(self.member_membership.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.owner_membership.refresh_from_db()
        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.owner_membership.role,
            WorkspaceMembership.Role.ADMIN,
        )
        self.assertEqual(
            self.member_membership.role,
            WorkspaceMembership.Role.OWNER,
        )

    def test_admin_cannot_transfer_ownership(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.transfer_url(),
            {"membership_id": str(self.member_membership.id)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_transfer_ownership_to_self(self):
        self.authenticate(self.owner)

        response = self.client.post(
            self.transfer_url(),
            {"membership_id": str(self.owner_membership.id)},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.owner_membership.refresh_from_db()
        self.assertEqual(
            self.owner_membership.role,
            WorkspaceMembership.Role.OWNER,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_owner_can_create_invitation_and_email_is_sent(self):
        response = self.create_invitation(" Invitee@Example.com ")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(response.data["email"], "invitee@example.com")
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invitee@example.com", mail.outbox[0].to)

        invitation = WorkspaceInvitation.objects.get(
            pk=response.data["id"],
        )
        self.assertEqual(
            len(invitation.token_hash),
            64,
        )
        self.assertNotIn(invitation.token_hash, mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_duplicate_pending_invitation_is_rejected(self):
        first = self.create_invitation()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.create_invitation()
        self.assertEqual(
            second.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_member_cannot_create_invitation(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.invitations_url(),
            {"email": "invitee@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_owner_can_revoke_pending_invitation(self):
        create_response = self.create_invitation()
        invitation_id = create_response.data["id"]

        response = self.client.delete(
            f"{self.invitations_url()}{invitation_id}/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        invitation = WorkspaceInvitation.objects.get(pk=invitation_id)
        self.assertEqual(
            invitation.status,
            WorkspaceInvitation.Status.REVOKED,
        )
        self.assertIsNotNone(invitation.revoked_at)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_verified_user_can_accept_invitation(self):
        invitee = self.create_user(
            "invitee@example.com",
            is_email_verified=True,
        )
        create_response = self.create_invitation()
        invitation = WorkspaceInvitation.objects.get(
            pk=create_response.data["id"],
        )

        # The raw token is sent by email; the database stores only its hash.
        email_body = mail.outbox[0].body
        invitation_url = next(
            line.strip()
            for line in email_body.splitlines()
            if "/accept-invitation/?" in line
        )
        raw_token = parse_qs(urlparse(invitation_url).query)["token"][0]

        self.authenticate(invitee)
        response = self.client.post(
            "/api/v1/workspaces/invitations/accept/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=invitee,
                role=WorkspaceMembership.Role.MEMBER,
            ).exists()
        )

        invitation.refresh_from_db()
        self.assertEqual(
            invitation.status,
            WorkspaceInvitation.Status.ACCEPTED,
        )
        self.assertIsNotNone(invitation.accepted_at)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_unverified_user_cannot_accept_invitation(self):
        invitee = self.create_user("invitee@example.com")
        create_response = self.create_invitation()
        invitation = WorkspaceInvitation.objects.get(
            pk=create_response.data["id"],
        )

        invitation_url = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/accept-invitation/?" in line
        )
        raw_token = parse_qs(urlparse(invitation_url).query)["token"][0]

        self.authenticate(invitee)
        response = self.client.post(
            "/api/v1/workspaces/invitations/accept/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=invitee,
            ).exists()
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_expired_invitation_cannot_be_accepted(self):
        invitee = self.create_user(
            "invitee@example.com",
            is_email_verified=True,
        )
        create_response = self.create_invitation()
        invitation = WorkspaceInvitation.objects.get(
            pk=create_response.data["id"],
        )

        invitation_url = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/accept-invitation/?" in line
        )
        raw_token = parse_qs(urlparse(invitation_url).query)["token"][0]

        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at"])

        self.authenticate(invitee)
        response = self.client.post(
            "/api/v1/workspaces/invitations/accept/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        invitation.refresh_from_db()
        self.assertEqual(
            invitation.status,
            WorkspaceInvitation.Status.EXPIRED,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_invitation_creation_is_throttled(self):
        cache.clear()

        with patch.object(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {"workspace_invitation": "5/hour"},
        ):
            for index in range(5):
                response = self.create_invitation(
                    f"invitee{index}@example.com",
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_201_CREATED,
                )

            response = self.create_invitation(
                "invitee-over-limit@example.com",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        self.assertEqual(
            WorkspaceInvitation.objects.filter(
                workspace=self.workspace,
            ).count(),
            5,
        )
        self.assertEqual(len(mail.outbox), 5)

    def test_non_member_with_invalid_invitation_body_gets_404(self):
        self.authenticate(self.outsider)

        response = self.client.post(
            self.invitations_url(),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_with_invalid_role_update_body_gets_403(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.role_url(self.member_membership),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_with_invalid_transfer_body_gets_403(self):
        self.authenticate(self.admin)

        response = self.client.post(
            self.transfer_url(),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_leave_error_has_detail_key(self):
        self.authenticate(self.owner)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIsInstance(response.data, dict)
        self.assertIn("detail", response.data)
        self.assertIsInstance(response.data["detail"], str)

    def test_expired_pending_invitation_is_listed_as_expired(self):
        create_response = self.create_invitation()
        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )

        invitation = WorkspaceInvitation.objects.get(
            pk=create_response.data["id"],
        )
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at"])

        self.authenticate(self.owner)
        response = self.client.get(self.invitations_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        serialized_invitation = next(
            item for item in response.data["results"]
            if item["id"] == str(invitation.id)
        )
        self.assertEqual(serialized_invitation["status"], "expired")

        # The API computes the effective status without mutating the database.
        invitation.refresh_from_db()
        self.assertEqual(
            invitation.status,
            WorkspaceInvitation.Status.PENDING,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_owner_can_resend_invitation_with_new_token(self):
        create_response = self.create_invitation()
        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )

        invitation = WorkspaceInvitation.objects.get(
            pk=create_response.data["id"],
        )
        original_token_hash = invitation.token_hash
        original_expiry = invitation.expires_at

        response = self.client.post(
            f"{self.invitations_url()}{invitation.id}/resend/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invitation.email, mail.outbox[0].to)

        invitation.refresh_from_db()

        self.assertNotEqual(invitation.token_hash, original_token_hash)
        self.assertGreater(invitation.expires_at, original_expiry)
        self.assertEqual(
            invitation.status,
            WorkspaceInvitation.Status.PENDING,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_revoked_invitation_cannot_be_resent(self):
        create_response = self.create_invitation()
        invitation_id = create_response.data["id"]

        revoke_response = self.client.delete(
            f"{self.invitations_url()}{invitation_id}/",
        )
        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            f"{self.invitations_url()}{invitation_id}/resend/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_member_cannot_resend_invitation(self):
        create_response = self.create_invitation()
        invitation_id = create_response.data["id"]

        self.authenticate(self.member)

        response = self.client.post(
            f"{self.invitations_url()}{invitation_id}/resend/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_workspace_list_supports_pagination(self):
        for index in range(2):
            workspace = Workspace.objects.create(
                name=f"Pagination Org {index}",
            )
            WorkspaceMembership.objects.create(
                workspace=workspace,
                user=self.owner,
                role=WorkspaceMembership.Role.OWNER,
            )

        self.authenticate(self.owner)
        response = self.client.get(
            f"{self.list_url}?page_size=2",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            f"{self.list_url}?page=2&page_size=2",
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)


    def test_member_list_supports_pagination(self):
        self.authenticate(self.member)
        response = self.client.get(
            f"{self.members_url()}?page_size=2",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            f"{self.members_url()}?page=2&page_size=2",
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 2)


    def test_invitation_list_supports_pagination(self):
        for index in range(3):
            WorkspaceInvitation.objects.create(
                workspace=self.workspace,
                email=f"page-{index}@example.com",
                invited_by=self.owner,
                token_hash=f"{index:064d}",
                expires_at=timezone.now() + timedelta(days=7),
            )

        self.authenticate(self.owner)
        response = self.client.get(
            f"{self.invitations_url()}?page_size=2",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            f"{self.invitations_url()}?page=2&page_size=2",
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)
