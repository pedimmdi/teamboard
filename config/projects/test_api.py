from unittest.mock import patch
from django.core.cache import cache
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ProjectAPITests(APITestCase):
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

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.url = reverse(
            "workspaces_api_v1:projects_api_v1:project-list-create",
            kwargs={"slug": self.workspace.slug},
        )

    def test_owner_can_create_project(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.url,
            {"name": "Website", "description": "New website"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(name="Website")
        self.assertTrue(
            ProjectMembership.objects.filter(
                project=project,
                user=self.owner,
                role=ProjectMembership.Role.MANAGER,
            ).exists()
        )

    def test_regular_workspace_member_cannot_create_project(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            self.url,
            {"name": "Unauthorized"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_list_projects(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_list_is_private(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_owner_sees_own_project(self):
        self.client.force_authenticate(user=self.owner)

        self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["role"],
            ProjectMembership.Role.MANAGER,
        )

    def test_duplicate_name_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        response = self.client.post(
            self.url,
            {"name": "website"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Project.objects.count(), 1)

    def test_anonymous_user_cannot_create_project(self):
        response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ),
        )


    def test_project_member_can_view_details(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
            },
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Private Project")

    def test_workspace_member_cannot_view_private_project(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
            },
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_project_manager_can_update_project(self):
        self.client.force_authenticate(user=self.owner)

        create_response = self.client.post(
            self.url,
            {"name": "Original"},
            format="json",
        )
        project_id = create_response.data["id"]

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
            },
        )

        response = self.client.patch(
            url,
            {
                "name": "Updated",
                "description": "New description",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated")

        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.description, "New description")

    def test_regular_project_member_cannot_update(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
            },
        )

        response = self.client.patch(
            url,
            {"name": "Unauthorized Update"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_update_rejects_duplicate_name(self):
        self.client.force_authenticate(user=self.owner)

        first = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        second = self.client.post(
            self.url,
            {"name": "Mobile App"},
            format="json",
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": second.data["id"],
            },
        )

        response = self.client.patch(
            url,
            {"name": "website"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Project.objects.get(pk=second.data["id"]).name,
            "Mobile App",
        )


    def test_manager_can_add_project_member(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
            },
        )

        response = self.client.post(
            url,
            {"user_id": self.member.pk, "role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ProjectMembership.objects.filter(
                project_id=project_id,
                user=self.member,
                role=ProjectMembership.Role.MEMBER,
            ).exists()
        )

    def test_regular_member_cannot_add_members(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        ProjectMembership.objects.create(
            project_id=project_id,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
            },
        )

        response = self.client.post(
            url,
            {"user_id": self.outsider.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_member_can_list_members(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        ProjectMembership.objects.create(
            project_id=project_id,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_outsider_cannot_list_project_members(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )

        self.client.force_authenticate(user=self.outsider)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_response.data["id"],
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_can_remove_regular_member(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        membership = ProjectMembership.objects.create(
            project_id=project_id,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-remove",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
                "membership_id": membership.pk,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ProjectMembership.objects.filter(pk=membership.pk).exists()
        )

    def test_last_manager_cannot_be_demoted(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        membership = ProjectMembership.objects.get(
            project_id=project_id,
            user=self.owner,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-role-update",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
                "membership_id": membership.pk,
            },
        )

        response = self.client.patch(
            url,
            {"role": "member"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        membership.refresh_from_db()
        self.assertEqual(
            membership.role,
            ProjectMembership.Role.MANAGER,
        )


    def test_cannot_add_user_outside_workspace(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_response.data["id"],
            },
        )

        response = self.client.post(
            url,
            {"user_id": self.outsider.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ProjectMembership.objects.filter(user=self.outsider).exists()
        )

    def test_project_manager_cannot_remove_another_manager(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        membership = ProjectMembership.objects.get(
            project_id=project_id,
            user=self.owner,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-remove",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
                "membership_id": membership.pk,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            ProjectMembership.objects.filter(pk=membership.pk).exists()
        )

    def test_member_cannot_change_project_roles(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        member_membership = ProjectMembership.objects.create(
            project_id=project_id,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=self.member)

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-role-update",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
                "membership_id": member_membership.pk,
            },
        )

        response = self.client.patch(
            url,
            {"role": "manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_workspace_owner_can_promote_project_member(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )
        project_id = project_response.data["id"]

        member_membership = ProjectMembership.objects.create(
            project_id=project_id,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-role-update",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_id,
                "membership_id": member_membership.pk,
            },
        )

        response = self.client.patch(
            url,
            {"role": "manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member_membership.refresh_from_db()
        self.assertEqual(
            member_membership.role,
            ProjectMembership.Role.MANAGER,
        )

    def test_cannot_modify_membership_from_another_project(self):
        self.client.force_authenticate(user=self.owner)

        first_response = self.client.post(
            self.url,
            {"name": "First Project"},
            format="json",
        )
        second_response = self.client.post(
            self.url,
            {"name": "Second Project"},
            format="json",
        )

        membership = ProjectMembership.objects.create(
            project_id=second_response.data["id"],
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-remove",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": first_response.data["id"],
                "membership_id": membership.pk,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            ProjectMembership.objects.filter(pk=membership.pk).exists()
        )

    def test_workspace_owner_without_project_membership_cannot_access(self):
        self.client.force_authenticate(user=self.owner)

        project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.member,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MANAGER,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


    def test_cannot_delete_using_role_update_endpoint(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )

        membership = ProjectMembership.objects.get(
            project_id=project_response.data["id"],
            user=self.owner,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-role-update",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_response.data["id"],
                "membership_id": membership.pk,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_cannot_patch_using_member_remove_endpoint(self):
        self.client.force_authenticate(user=self.owner)

        project_response = self.client.post(
            self.url,
            {"name": "Website"},
            format="json",
        )

        membership = ProjectMembership.objects.get(
            project_id=project_response.data["id"],
            user=self.owner,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-remove",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project_response.data["id"],
                "membership_id": membership.pk,
            },
        )

        response = self.client.patch(
            url,
            {"role": "member"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


    def test_project_creation_is_throttled(self):
        cache.clear()
        self.client.force_authenticate(user=self.owner)

        with patch(
            "rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES",
            {
                "project_create": "1/hour",
                "project_member_add": "1/hour",
            },
        ):
            first = self.client.post(
                self.url,
                {"name": "First Project"},
                format="json",
            )

            second = self.client.post(
                self.url,
                {"name": "Second Project"},
                format="json",
            )

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            second.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


    def test_project_member_add_is_throttled(self):
        cache.clear()

        project = Project.objects.create(
            workspace=self.workspace,
            name="Website",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        url = reverse(
            "workspaces_api_v1:projects_api_v1:project-member-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
            },
        )

        self.client.force_authenticate(user=self.owner)

        with patch(
            "rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES",
            {
                "project_create": "1/hour",
                "project_member_add": "1/hour",
            },
        ):
            first = self.client.post(
                url,
                {"user_id": self.member.pk},
                format="json",
            )

            second = self.client.post(
                url,
                {"user_id": self.member.pk},
                format="json",
            )

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            second.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.assertEqual(
            ProjectMembership.objects.filter(
                project=project,
            ).count(),
            2,
        )
