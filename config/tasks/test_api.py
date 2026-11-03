from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="task-owner@example.com",
            password="Strong-password-2026!",
        )
        self.admin = User.objects.create_user(
            email="task-admin@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="task-member@example.com",
            password="Strong-password-2026!",
        )
        self.workspace_member = User.objects.create_user(
            email="workspace-only@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="task-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Task API Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.admin, WorkspaceMembership.Role.ADMIN),
            (self.member, WorkspaceMembership.Role.MEMBER),
            (
                self.workspace_member,
                WorkspaceMembership.Role.MEMBER,
            ),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Task API Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.list_url = self.get_list_url(self.project)

    def get_list_url(self, project):
        return reverse(
            "workspaces_api_v1:tasks_api_v1:task-list-create",
            kwargs={
                "slug": project.workspace.slug,
                "project_id": project.pk,
            },
        )

    def get_detail_url(self, task):
        return reverse(
            "workspaces_api_v1:tasks_api_v1:task-detail",
            kwargs={
                "slug": task.project.workspace.slug,
                "project_id": task.project_id,
                "task_id": task.pk,
            },
        )

    def create_task(self, **kwargs):
        return Task.objects.create(
            project=self.project,
            title=kwargs.pop("title", "Example Task"),
            created_by=self.owner,
            **kwargs,
        )

    def test_project_member_can_create_task(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            self.list_url,
            {"title": "Implement API"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.title, "Implement API")
        self.assertEqual(task.created_by, self.member)
        self.assertEqual(task.project, self.project)
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_workspace_admin_can_create_without_project_membership(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.list_url,
            {"title": "Admin Task"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_workspace_only_member_cannot_access_tasks(self):
        self.client.force_authenticate(
            user=self.workspace_member,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_outsider_cannot_create_task(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            self.list_url,
            {"title": "Unauthorized"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertFalse(
            Task.objects.filter(title="Unauthorized").exists()
        )

    def test_anonymous_user_cannot_list_tasks(self):
        response = self.client.get(self.list_url)

        self.assertIn(
            response.status_code,
            (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ),
        )

    def test_project_member_can_list_tasks(self):
        self.create_task(title="First Task")
        self.create_task(title="Second Task")

        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_task_list_is_scoped_to_project(self):
        self.create_task(title="Visible Task")

        other_project = Project.objects.create(
            workspace=self.workspace,
            name="Other Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=other_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        Task.objects.create(
            project=other_project,
            title="Hidden Task",
        )

        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.list_url)

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["title"],
            "Visible Task",
        )

    def test_task_list_pagination(self):
        for index in range(25):
            self.create_task(title=f"Task {index}")

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            self.list_url,
            {"page": 2},
        )

        self.assertEqual(
            len(second_page.data["results"]),
            5,
        )

    def test_project_member_can_retrieve_task(self):
        task = self.create_task()

        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            self.get_detail_url(task),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            str(response.data["id"]),
            str(task.pk),
        )

    def test_project_member_can_update_task(self):
        task = self.create_task()

        self.client.force_authenticate(user=self.member)

        response = self.client.patch(
            self.get_detail_url(task),
            {
                "title": "Updated Task",
                "status": "in_progress",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        task.refresh_from_db()
        self.assertEqual(task.title, "Updated Task")
        self.assertEqual(task.status, "in_progress")

    def test_patch_omitted_assignee_does_not_clear_it(self):
        task = self.create_task(assignee=self.member)

        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.get_detail_url(task),
            {"status": "done"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        task.refresh_from_db()
        self.assertEqual(task.assignee, self.member)

    def test_patch_null_assignee_clears_it(self):
        task = self.create_task(assignee=self.member)

        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.get_detail_url(task),
            {"assignee": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_invalid_assignee_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "title": "Invalid Assignment",
                "assignee": self.outsider.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("assignee", response.data)

    def test_invalid_status_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "title": "Invalid Status",
                "status": "unknown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_invalid_priority_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "title": "Invalid Priority",
                "priority": "critical",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("priority", response.data)

    def test_blank_title_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"title": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)

    def test_empty_patch_is_rejected(self):
        task = self.create_task()

        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.get_detail_url(task),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_regular_project_member_cannot_delete_task(self):
        task = self.create_task()

        self.client.force_authenticate(user=self.member)

        response = self.client.delete(
            self.get_detail_url(task),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertTrue(
            Task.objects.filter(pk=task.pk).exists()
        )

    def test_workspace_admin_can_delete_task(self):
        task = self.create_task()

        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(
            self.get_detail_url(task),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Task.objects.filter(pk=task.pk).exists()
        )

    def test_task_cannot_be_accessed_through_other_project(self):
        task = self.create_task()

        other_project = Project.objects.create(
            workspace=self.workspace,
            name="Second Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=other_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        wrong_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": other_project.pk,
                "task_id": task.pk,
            },
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(wrong_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_task_create_is_throttled(self):
        from rest_framework.throttling import ScopedRateThrottle

        cache.clear()

        try:
            with patch.dict(
                ScopedRateThrottle.THROTTLE_RATES,
                {"task_create": "2/hour"},
            ):
                self.client.force_authenticate(user=self.owner)

                for index in range(2):
                    response = self.client.post(
                        self.list_url,
                        {"title": f"Throttled Task {index}"},
                        format="json",
                    )
                    self.assertEqual(
                        response.status_code,
                        status.HTTP_201_CREATED,
                    )

                response = self.client.post(
                    self.list_url,
                    {"title": "Third Task"},
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                )
        finally:
            cache.clear()

    def test_task_response_includes_user_details(self):
        task = self.create_task(
            title="Task with user details",
            assignee=self.member,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.get_detail_url(task),
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["assignee"],
            self.member.pk,
        )
        self.assertEqual(
            response.data["assignee_email"],
            self.member.email,
        )
        self.assertIsNone(
            response.data["assignee_avatar"],
        )

        self.assertEqual(
            response.data["created_by"],
            self.owner.pk,
        )
        self.assertEqual(
            response.data["created_by_email"],
            self.owner.email,
        )
        self.assertIsNone(
            response.data["created_by_avatar"],
        )

    def test_creator_email_remains_after_leaving_project(self):
        task = self.create_task(
            title="Task created by former member",
        )

        # Ensure the project keeps an eligible manager.
        ProjectMembership.objects.create(
            project=self.project,
            user=self.admin,
            role=ProjectMembership.Role.MANAGER,
        )

        # The task creator leaves the project.
        ProjectMembership.objects.filter(
            project=self.project,
            user=self.owner,
        ).delete()

        self.assertFalse(
            ProjectMembership.objects.filter(
                project=self.project,
                user=self.owner,
            ).exists()
        )

        # Another manager retrieves the task.
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            self.get_detail_url(task),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["created_by"],
            self.owner.pk,
        )
        self.assertEqual(
            response.data["created_by_email"],
            self.owner.email,
        )

    def test_task_list_does_not_have_n_plus_one_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_authenticate(user=self.owner)

        self.create_task(
            title="Task 1",
            assignee=self.member,
        )

        with CaptureQueriesContext(connection) as small_queries:
            small_response = self.client.get(self.list_url)

        self.assertEqual(small_response.status_code, 200)

        for index in range(2, 11):
            self.create_task(
                title=f"Task {index}",
                assignee=self.member,
            )

        with CaptureQueriesContext(connection) as large_queries:
            large_response = self.client.get(self.list_url)

        self.assertEqual(large_response.status_code, 200)

        self.assertEqual(
            len(small_queries),
            len(large_queries),
            "Task list query count increased with more tasks.",
        )
