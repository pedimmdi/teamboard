from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from organizations.services import hash_invitation_token


User = get_user_model()


class OrganizationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="Strong-password-2026!",
        )

    def test_organization_slug_has_ten_characters(self):
        organization = Organization.objects.create(
            name="TeamBoard",
        )

        self.assertEqual(len(organization.slug), 10)
        self.assertRegex(organization.slug, r"^[a-z0-9]{10}$")

    def test_organization_names_can_be_duplicated(self):
        first = Organization.objects.create(name="TeamBoard")
        second = Organization.objects.create(name="TeamBoard")

        self.assertEqual(first.name, second.name)
        self.assertNotEqual(first.slug, second.slug)

    def test_user_can_have_only_one_membership_per_organization(self):
        organization = Organization.objects.create(name="TeamBoard")

        OrganizationMembership.objects.create(
            organization=organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.create(
                    organization=organization,
                    user=self.user,
                    role=OrganizationMembership.Role.MEMBER,
                )


class OrganizationAPITests(APITestCase):
    list_url = "/api/v1/organizations/"

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

    def create_organization(self, user, name="TeamBoard"):
        self.authenticate(user)

        return self.client.post(
            self.list_url,
            {"name": name},
            format="json",
        )

    def test_organization_creation_assigns_creator_as_owner(self):
        response = self.create_organization(self.owner)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        organization = Organization.objects.get(
            slug=response.data["slug"],
        )
        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=self.owner,
        )

        self.assertEqual(membership.role, OrganizationMembership.Role.OWNER)
        self.assertEqual(len(organization.slug), 10)
        self.assertEqual(
            response.data["role"],
            OrganizationMembership.Role.OWNER,
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

        organization = Organization.objects.get(
            slug=response.data["slug"],
        )
        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=self.owner,
        )

        self.assertNotEqual(organization.slug, "customslug")
        self.assertEqual(membership.role, OrganizationMembership.Role.OWNER)

    def test_unauthenticated_user_cannot_list_organizations(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unauthenticated_user_cannot_create_organization(self):
        response = self.client.post(
            self.list_url,
            {"name": "TeamBoard"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(Organization.objects.count(), 0)

    def test_user_sees_only_organizations_they_belong_to(self):
        own_response = self.create_organization(
            self.owner,
            "Owner Organization",
        )
        self.assertEqual(
            own_response.status_code,
            status.HTTP_201_CREATED,
        )

        other_response = self.create_organization(
            self.member,
            "Member Organization",
        )
        self.assertEqual(
            other_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.authenticate(self.owner)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["name"],
            "Owner Organization",
        )
        self.assertEqual(
            response.data[0]["role"],
            OrganizationMembership.Role.OWNER,
        )

    def test_non_member_cannot_retrieve_organization(self):
        create_response = self.create_organization(self.owner)
        slug = create_response.data["slug"]

        self.authenticate(self.outsider)
        response = self.client.get(
            f"{self.list_url}{slug}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_member_can_retrieve_organization(self):
        create_response = self.create_organization(self.owner)
        slug = create_response.data["slug"]

        OrganizationMembership.objects.create(
            organization=Organization.objects.get(slug=slug),
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
        )

        self.authenticate(self.member)
        response = self.client.get(
            f"{self.list_url}{slug}/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], slug)
        self.assertEqual(
            response.data["role"],
            OrganizationMembership.Role.MEMBER,
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
        self.assertEqual(Organization.objects.count(), 0)

    def test_organization_creation_is_throttled(self):
        cache.clear()

        for index in range(5):
            response = self.create_organization(
                self.owner,
                name=f"TeamBoard {index}",
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )

        response = self.create_organization(
            self.owner,
            name="TeamBoard over limit",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


class OrganizationManagementAPITests(APITestCase):
    list_url = "/api/v1/organizations/"

    def setUp(self):
        self.owner = self.create_user("owner@example.com")
        self.admin = self.create_user("admin@example.com")
        self.member = self.create_user("member@example.com")
        self.other_member = self.create_user("other@example.com")
        self.outsider = self.create_user("outsider@example.com")

        self.organization = Organization.objects.create(
            name="TeamBoard",
        )

        self.owner_membership = self.add_member(
            self.owner,
            OrganizationMembership.Role.OWNER,
        )
        self.admin_membership = self.add_member(
            self.admin,
            OrganizationMembership.Role.ADMIN,
        )
        self.member_membership = self.add_member(
            self.member,
            OrganizationMembership.Role.MEMBER,
        )
        self.other_membership = self.add_member(
            self.other_member,
            OrganizationMembership.Role.MEMBER,
        )

    def create_user(self, email, **extra_fields):
        return User.objects.create_user(
            email=email,
            password="Strong-password-2026!",
            **extra_fields,
        )

    def add_member(self, user, role):
        return OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=role,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def organization_url(self):
        return f"{self.list_url}{self.organization.slug}/"

    def members_url(self):
        return f"{self.organization_url()}members/"

    def membership_url(self, membership):
        return f"{self.members_url()}{membership.id}/"

    def role_url(self, membership):
        return f"{self.membership_url(membership)}role/"

    def leave_url(self):
        return f"{self.organization_url()}leave/"

    def transfer_url(self):
        return f"{self.organization_url()}transfer-ownership/"

    def invitations_url(self):
        return f"{self.organization_url()}invitations/"

    def create_invitation(self, email="invitee@example.com"):
        self.authenticate(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.invitations_url(),
                {"email": email},
                format="json",
            )

        return response

    def test_owner_can_update_organization_name(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.organization_url(),
            {"name": "Updated Team"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Updated Team")

    def test_patch_nonexistent_organization_returns_404(self):
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

    def test_admin_can_update_organization_name(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.organization_url(),
            {"name": "Admin Updated Team"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "Admin Updated Team")

    def test_member_cannot_update_organization(self):
        self.authenticate(self.member)

        response = self.client.patch(
            self.organization_url(),
            {"name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, "TeamBoard")

    def test_outsider_cannot_update_organization(self):
        self.authenticate(self.outsider)

        response = self.client.patch(
            self.organization_url(),
            {"name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_rejects_blank_name(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.organization_url(),
            {"name": "   "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_update_does_not_allow_changing_slug(self):
        original_slug = self.organization.slug
        self.authenticate(self.owner)

        response = self.client.patch(
            self.organization_url(),
            {
                "name": "Updated Team",
                "slug": "customslug",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.slug, original_slug)

    def test_owner_can_delete_organization_without_deleting_users(self):
        self.authenticate(self.owner)

        response = self.client.delete(self.organization_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Organization.objects.filter(pk=self.organization.pk).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization_id=self.organization.pk,
            ).exists()
        )

    def test_admin_cannot_delete_organization(self):
        self.authenticate(self.admin)

        response = self.client.delete(self.organization_url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            Organization.objects.filter(pk=self.organization.pk).exists()
        )

    def test_member_cannot_delete_organization(self):
        self.authenticate(self.member)

        response = self.client.delete(self.organization_url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_leave_organization(self):
        self.authenticate(self.member)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.member,
            ).exists()
        )
        self.assertTrue(
            Organization.objects.filter(pk=self.organization.pk).exists()
        )
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_admin_can_leave_organization(self):
        self.authenticate(self.admin)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.admin,
            ).exists()
        )

    def test_owner_cannot_leave_organization(self):
        self.authenticate(self.owner)

        response = self.client.post(self.leave_url())

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.owner,
                role=OrganizationMembership.Role.OWNER,
            ).exists()
        )

    def test_non_member_cannot_leave_organization(self):
        self.authenticate(self.outsider)

        response = self.client.post(self.leave_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_can_view_member_list(self):
        self.authenticate(self.member)

        response = self.client.get(self.members_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

        current_user_rows = [
            row for row in response.data
            if row["is_current_user"]
        ]
        self.assertEqual(len(current_user_rows), 1)

        current_user_row = current_user_rows[0]
        self.assertEqual(
            current_user_row["user_id"],
            self.member.pk,
        )
        self.assertEqual(
            current_user_row["user_email"],
            self.member.email,
        )
        self.assertEqual(
            current_user_row["role"],
            OrganizationMembership.Role.MEMBER,
        )

        self.assertTrue(
            all("user_id" in row for row in response.data)
        )

    def test_outsider_cannot_view_member_list(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.members_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_promote_member_to_admin(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.member_membership),
            {"role": OrganizationMembership.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertEqual(
            self.member_membership.role,
            OrganizationMembership.Role.ADMIN,
        )

    def test_owner_can_demote_admin_to_member(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.admin_membership),
            {"role": OrganizationMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin_membership.refresh_from_db()
        self.assertEqual(
            self.admin_membership.role,
            OrganizationMembership.Role.MEMBER,
        )

    def test_admin_cannot_change_member_roles(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            self.role_url(self.member_membership),
            {"role": OrganizationMembership.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_role_cannot_be_changed_through_role_endpoint(self):
        self.authenticate(self.owner)

        response = self.client.patch(
            self.role_url(self.owner_membership),
            {"role": OrganizationMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.owner_membership.refresh_from_db()
        self.assertEqual(
            self.owner_membership.role,
            OrganizationMembership.Role.OWNER,
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
            OrganizationMembership.objects.filter(
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
        self.other_membership.role = OrganizationMembership.Role.ADMIN
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
            OrganizationMembership.objects.filter(
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
            OrganizationMembership.objects.filter(
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
            OrganizationMembership.Role.ADMIN,
        )
        self.assertEqual(
            self.member_membership.role,
            OrganizationMembership.Role.OWNER,
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
            OrganizationMembership.Role.OWNER,
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

        invitation = OrganizationInvitation.objects.get(
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

        invitation = OrganizationInvitation.objects.get(pk=invitation_id)
        self.assertEqual(
            invitation.status,
            OrganizationInvitation.Status.REVOKED,
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
        invitation = OrganizationInvitation.objects.get(
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
            "/api/v1/organizations/invitations/accept/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=invitee,
                role=OrganizationMembership.Role.MEMBER,
            ).exists()
        )

        invitation.refresh_from_db()
        self.assertEqual(
            invitation.status,
            OrganizationInvitation.Status.ACCEPTED,
        )
        self.assertIsNotNone(invitation.accepted_at)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_unverified_user_cannot_accept_invitation(self):
        invitee = self.create_user("invitee@example.com")
        create_response = self.create_invitation()
        invitation = OrganizationInvitation.objects.get(
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
            "/api/v1/organizations/invitations/accept/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
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
        invitation = OrganizationInvitation.objects.get(
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
            "/api/v1/organizations/invitations/accept/",
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
            OrganizationInvitation.Status.EXPIRED,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_invitation_creation_is_throttled(self):
        cache.clear()

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
            OrganizationInvitation.objects.filter(
                organization=self.organization,
            ).count(),
            5,
        )
        self.assertEqual(len(mail.outbox), 5)
