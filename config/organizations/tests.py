
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from organizations.models import Organization, OrganizationMembership


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
        self.assertNotIn("role", response.data)

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
