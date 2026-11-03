from datetime import date
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

    def test_workspace_privileged_users_manage_tasks_without_project_membership(self):
        for actor in (self.owner, self.admin):
            with self.subTest(actor=actor.email):
                project = Project.objects.create(
                    workspace=self.workspace,
                    name=f"Privileged Tasks {actor.pk}",
                    created_by=self.owner,
                )

                ProjectMembership.objects.create(
                    project=project,
                    user=self.member,
                    role=ProjectMembership.Role.MANAGER,
                )

                self.assertFalse(
                    ProjectMembership.objects.filter(
                        project=project,
                        user=actor,
                    ).exists()
                )

                self.client.force_authenticate(user=actor)

                list_url = self.get_list_url(project)

                create_response = self.client.post(
                    list_url,
                    {"title": "Privileged Task"},
                    format="json",
                )
                self.assertEqual(
                    create_response.status_code,
                    status.HTTP_201_CREATED,
                    create_response.data,
                )

                task = Task.objects.get(
                    pk=create_response.data["id"]
                )

                update_response = self.client.patch(
                    self.get_detail_url(task),
                    {"title": "Updated Privileged Task"},
                    format="json",
                )
                self.assertEqual(
                    update_response.status_code,
                    status.HTTP_200_OK,
                    update_response.data,
                )

                move_url = reverse(
                    "workspaces_api_v1:tasks_api_v1:task-move",
                    kwargs={
                        "slug": self.workspace.slug,
                        "project_id": project.pk,
                        "task_id": task.pk,
                    },
                )

                move_response = self.client.post(
                    move_url,
                    {
                        "status": Task.Status.IN_PROGRESS,
                        "position": 0,
                    },
                    format="json",
                )
                self.assertEqual(
                    move_response.status_code,
                    status.HTTP_200_OK,
                    move_response.data,
                )

                task.refresh_from_db()
                self.assertEqual(
                    task.title,
                    "Updated Privileged Task",
                )
                self.assertEqual(
                    task.status,
                    Task.Status.IN_PROGRESS,
                )
                self.assertEqual(task.position, 0)

                delete_response = self.client.delete(
                    self.get_detail_url(task)
                )
                self.assertEqual(
                    delete_response.status_code,
                    status.HTTP_204_NO_CONTENT,
                )
                self.assertFalse(
                    Task.objects.filter(pk=task.pk).exists()
                )

    def test_workspace_privileged_users_cannot_assign_themselves_without_project_membership(self):
        for actor in (self.owner, self.admin):
            with self.subTest(actor=actor.email):
                project = Project.objects.create(
                    workspace=self.workspace,
                    name=f"Assignee Policy {actor.pk}",
                    created_by=self.owner,
                )

                ProjectMembership.objects.create(
                    project=project,
                    user=self.member,
                    role=ProjectMembership.Role.MANAGER,
                )

                self.client.force_authenticate(user=actor)

                create_response = self.client.post(
                    self.get_list_url(project),
                    {
                        "title": "Invalid Assignment",
                        "assignee": str(actor.pk),
                    },
                    format="json",
                )
                self.assertEqual(
                    create_response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    create_response.data,
                )
                self.assertIn(
                    "assignee",
                    create_response.data,
                )

                task = Task.objects.create(
                    project=project,
                    title="Unassigned Task",
                    created_by=self.member,
                    position=0,
                )

                update_response = self.client.patch(
                    self.get_detail_url(task),
                    {"assignee": str(actor.pk)},
                    format="json",
                )
                self.assertEqual(
                    update_response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    update_response.data,
                )
                self.assertIn(
                    "assignee",
                    update_response.data,
                )

                task.refresh_from_db()
                self.assertIsNone(task.assignee_id)

    def test_workspace_member_without_project_membership_cannot_manage_tasks(self):
        project = Project.objects.create(
            workspace=self.workspace,
            name="Restricted Tasks Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MANAGER,
        )

        task = Task.objects.create(
            project=project,
            title="Protected Task",
            created_by=self.member,
            position=0,
        )

        self.client.force_authenticate(
            user=self.workspace_member
        )

        create_response = self.client.post(
            self.get_list_url(project),
            {"title": "Forbidden Task"},
            format="json",
        )

        update_response = self.client.patch(
            self.get_detail_url(task),
            {"title": "Forbidden Update"},
            format="json",
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": project.pk,
                "task_id": task.pk,
            },
        )

        move_response = self.client.post(
            move_url,
            {
                "status": Task.Status.DONE,
                "position": 0,
            },
            format="json",
        )

        delete_response = self.client.delete(
            self.get_detail_url(task)
        )

        for response in (
            create_response,
            update_response,
            move_response,
            delete_response,
        ):
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
                response.data,
            )

        task.refresh_from_db()
        self.assertEqual(task.title, "Protected Task")
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_create_assignee_errors_do_not_reveal_user_existence(self):
        self.client.force_authenticate(user=self.owner)

        responses = []

        for assignee_id in (
            str(self.outsider.pk),
            str(self.workspace_member.pk),
            str(10**15),
        ):
            with self.subTest(assignee_id=assignee_id):
                response = self.client.post(
                    self.list_url,
                    {
                        "title": "Private Assignment",
                        "assignee": assignee_id,
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("assignee", response.data)
                responses.append(response.data)

        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[1], responses[2])

        self.assertFalse(
            Task.objects.filter(
                title="Private Assignment",
            ).exists()
        )

    def test_update_assignee_errors_do_not_reveal_user_existence(self):
        task = self.create_task(
            title="Protected Assignment",
        )

        self.client.force_authenticate(user=self.owner)

        responses = []

        for assignee_id in (
            str(self.outsider.pk),
            str(self.workspace_member.pk),
            str(10**15),
        ):
            with self.subTest(assignee_id=assignee_id):
                response = self.client.patch(
                    self.get_detail_url(task),
                    {"assignee": assignee_id},
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("assignee", response.data)
                responses.append(response.data)

        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[1], responses[2])

        task.refresh_from_db()
        self.assertIsNone(task.assignee_id)

    def test_create_and_update_accept_eligible_project_assignee(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {
                "title": "Valid Assignment",
                "assignee": str(self.member.pk),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.assignee_id, self.member.pk)

        unassign_response = self.client.patch(
            self.get_detail_url(task),
            {"assignee": None},
            format="json",
        )

        self.assertEqual(
            unassign_response.status_code,
            status.HTTP_200_OK,
            unassign_response.data,
        )

        task.refresh_from_db()
        self.assertIsNone(task.assignee_id)

        reassign_response = self.client.patch(
            self.get_detail_url(task),
            {"assignee": str(self.member.pk)},
            format="json",
        )

        self.assertEqual(
            reassign_response.status_code,
            status.HTTP_200_OK,
            reassign_response.data,
        )

        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.member.pk)

    def test_invalid_assignee_does_not_modify_other_task_fields(self):
        task = self.create_task(
            title="Original Title",
            priority=Task.Priority.MEDIUM,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.get_detail_url(task),
            {
                "title": "Should Not Be Saved",
                "priority": Task.Priority.URGENT,
                "assignee": str(self.outsider.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        task.refresh_from_db()
        self.assertEqual(task.title, "Original Title")
        self.assertEqual(task.priority, Task.Priority.MEDIUM)
        self.assertIsNone(task.assignee_id)

    def test_created_task_has_initial_position(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            self.list_url,
            {"title": "First Kanban Task"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertIn("position", response.data)
        self.assertEqual(response.data["position"], 0)

        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.position, 0)

    def test_new_tasks_get_sequential_positions(self):
        self.client.force_authenticate(user=self.member)

        first_response = self.client.post(
            self.list_url,
            {"title": "First Task"},
            format="json",
        )
        second_response = self.client.post(
            self.list_url,
            {"title": "Second Task"},
            format="json",
        )
        third_response = self.client.post(
            self.list_url,
            {"title": "Third Task"},
            format="json",
        )

        for response in (
            first_response,
            second_response,
            third_response,
        ):
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )

        self.assertEqual(
            [
                first_response.data["position"],
                second_response.data["position"],
                third_response.data["position"],
            ],
            [0, 1, 2],
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position")
                .values_list("position", flat=True)
            ),
            [0, 1, 2],
        )

    def test_positions_are_independent_per_status(self):
        self.client.force_authenticate(user=self.member)

        tasks = [
            ("Todo 1", Task.Status.TODO),
            ("Progress 1", Task.Status.IN_PROGRESS),
            ("Todo 2", Task.Status.TODO),
            ("Progress 2", Task.Status.IN_PROGRESS),
        ]

        positions = []

        for title, task_status in tasks:
            response = self.client.post(
                self.list_url,
                {
                    "title": title,
                    "status": task_status,
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )

            positions.append(response.data["position"])

        self.assertEqual(positions, [0, 0, 1, 1])

    def test_positions_are_independent_per_project(self):
        self.client.force_authenticate(user=self.member)

        first_response = self.client.post(
            self.list_url,
            {"title": "Project One Task"},
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        other_project = Project.objects.create(
            workspace=self.workspace,
            name="Another Kanban Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=other_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        ProjectMembership.objects.create(
            project=other_project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        second_response = self.client.post(
            self.get_list_url(other_project),
            {"title": "Project Two Task"},
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(first_response.data["position"], 0)
        self.assertEqual(second_response.data["position"], 0)

    def test_status_change_moves_task_to_end_of_destination(self):
        self.client.force_authenticate(user=self.member)

        moving_task = self.create_task(
            title="Moving Task",
            status=Task.Status.TODO,
            position=0,
        )

        existing_task = self.create_task(
            title="Existing Progress Task",
            status=Task.Status.IN_PROGRESS,
            position=0,
        )

        response = self.client.patch(
            self.get_detail_url(moving_task),
            {"status": Task.Status.IN_PROGRESS},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        moving_task.refresh_from_db()
        existing_task.refresh_from_db()

        self.assertEqual(
            moving_task.status,
            Task.Status.IN_PROGRESS,
        )
        self.assertEqual(moving_task.position, 1)
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(existing_task.position, 0)

    def test_status_update_to_same_status_preserves_position(self):
        self.client.force_authenticate(user=self.member)

        first_task = self.create_task(
            title="First Task",
            status=Task.Status.TODO,
            position=0,
        )

        second_task = self.create_task(
            title="Second Task",
            status=Task.Status.TODO,
            position=1,
        )

        response = self.client.patch(
            self.get_detail_url(first_task),
            {"status": Task.Status.TODO},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        first_task.refresh_from_db()
        second_task.refresh_from_db()

        self.assertEqual(first_task.position, 0)
        self.assertEqual(second_task.position, 1)

    def test_regular_task_update_preserves_position(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Original Title",
            status=Task.Status.TODO,
            position=2,
        )

        response = self.client.patch(
            self.get_detail_url(task),
            {"title": "Updated Title"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        task.refresh_from_db()

        self.assertEqual(task.title, "Updated Title")
        self.assertEqual(task.position, 2)

    def test_move_task_reorders_within_same_status(self):
        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            position=0,
        )
        second = self.create_task(
            title="Second",
            position=1,
        )
        third = self.create_task(
            title="Third",
            position=2,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": third.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.TODO,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position")
                .values_list("pk", flat=True)
            ),
            [third.pk, first.pk, second.pk],
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position")
                .values_list("position", flat=True)
            ),
            [0, 1, 2],
        )

    def test_move_task_between_status_columns(self):
        self.client.force_authenticate(user=self.member)

        source_first = self.create_task(
            title="Source First",
            status=Task.Status.TODO,
            position=0,
        )
        moving = self.create_task(
            title="Moving",
            status=Task.Status.TODO,
            position=1,
        )
        source_last = self.create_task(
            title="Source Last",
            status=Task.Status.TODO,
            position=2,
        )
        destination = self.create_task(
            title="Destination",
            status=Task.Status.IN_PROGRESS,
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": moving.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position")
                .values_list("pk", "position")
            ),
            [
                (source_first.pk, 0),
                (source_last.pk, 1),
            ],
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.IN_PROGRESS,
                )
                .order_by("position")
                .values_list("pk", "position")
            ),
            [
                (moving.pk, 0),
                (destination.pk, 1),
            ],
        )

    def test_move_task_rejects_out_of_range_position(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Unchanged Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.TODO,
                "position": 99,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_move_task_rejects_negative_position(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Negative Position Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.TODO,
                "position": -1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        task.refresh_from_db()
        self.assertEqual(task.position, 0)

    def test_move_task_to_same_position_is_idempotent(self):
        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            position=0,
        )
        second = self.create_task(
            title="Second",
            position=1,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": second.pk,
            },
        )

        for _ in range(2):
            response = self.client.post(
                move_url,
                {
                    "status": Task.Status.TODO,
                    "position": 1,
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
            )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position")
                .values_list("pk", "position")
            ),
            [
                (first.pk, 0),
                (second.pk, 1),
            ],
        )

    def test_status_change_compacts_source_positions(self):
        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            status=Task.Status.TODO,
            position=0,
        )
        moving = self.create_task(
            title="Moving",
            status=Task.Status.TODO,
            position=1,
        )
        last = self.create_task(
            title="Last",
            status=Task.Status.TODO,
            position=2,
        )

        response = self.client.patch(
            self.get_detail_url(moving),
            {"status": Task.Status.IN_PROGRESS},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position", "pk")
                .values_list("pk", "position")
            ),
            [
                (first.pk, 0),
                (last.pk, 1),
            ],
        )

        moving.refresh_from_db()
        self.assertEqual(moving.position, 0)

    def test_deleting_task_compacts_remaining_positions(self):
        self.client.force_authenticate(user=self.owner)

        first = self.create_task(
            title="First",
            position=0,
        )
        middle = self.create_task(
            title="Middle",
            position=1,
        )
        last = self.create_task(
            title="Last",
            position=2,
        )

        response = self.client.delete(
            self.get_detail_url(middle),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            Task.objects.filter(pk=middle.pk).exists()
        )

        self.assertEqual(
            list(
                Task.objects.filter(
                    project=self.project,
                    status=Task.Status.TODO,
                )
                .order_by("position", "pk")
                .values_list("pk", "position")
            ),
            [
                (first.pk, 0),
                (last.pk, 1),
            ],
        )

    def test_list_tasks_can_order_by_position(self):
        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            status=Task.Status.TODO,
            position=0,
        )
        second = self.create_task(
            title="Second",
            status=Task.Status.TODO,
            position=1,
        )
        third = self.create_task(
            title="Third",
            status=Task.Status.TODO,
            position=2,
        )

        response = self.client.get(
            self.list_url,
            {
                "status": Task.Status.TODO,
                "ordering": "position",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            [
                item["id"]
                for item in response.data["results"]
            ],
            [
                str(first.pk),
                str(second.pk),
                str(third.pk),
            ],
        )

        self.assertEqual(
            [
                item["position"]
                for item in response.data["results"]
            ],
            [0, 1, 2],
        )

    def test_unauthenticated_user_cannot_move_task(self):
        task = self.create_task(
            title="Protected Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ),
        )

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_outsider_cannot_move_task(self):
        self.client.force_authenticate(user=self.outsider)

        task = self.create_task(
            title="Private Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_workspace_member_without_project_access_cannot_move_task(self):
        self.client.force_authenticate(
            user=self.workspace_member,
        )

        task = self.create_task(
            title="Project Private Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_move_task_cannot_cross_project_boundary(self):
        self.client.force_authenticate(user=self.member)

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

        ProjectMembership.objects.create(
            project=other_project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )

        task = Task.objects.create(
            project=other_project,
            title="Other Project Task",
            created_by=self.owner,
            status=Task.Status.TODO,
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        task.refresh_from_db()
        self.assertEqual(task.project_id, other_project.pk)
        self.assertEqual(task.status, Task.Status.TODO)
        self.assertEqual(task.position, 0)

    def test_move_task_updates_timestamp_only_for_moved_task(self):
        from datetime import timedelta
        from django.utils import timezone

        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            status=Task.Status.TODO,
            position=0,
        )
        second = self.create_task(
            title="Second",
            status=Task.Status.TODO,
            position=1,
        )

        old_timestamp = timezone.now() - timedelta(days=1)

        Task.objects.filter(
            pk__in=[first.pk, second.pk],
        ).update(updated_at=old_timestamp)

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": second.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.TODO,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(first.position, 1)
        self.assertEqual(second.position, 0)

        self.assertEqual(
            first.updated_at,
            old_timestamp,
        )

        self.assertGreater(
            second.updated_at,
            old_timestamp,
        )

    def test_move_task_requires_status(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {"position": 0},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("status", response.data)

    def test_move_task_requires_position(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {"status": Task.Status.TODO},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("position", response.data)

    def test_move_task_rejects_invalid_status(self):
        self.client.force_authenticate(user=self.member)

        task = self.create_task(
            title="Task",
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": "invalid_status",
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("status", response.data)

    def test_invalid_move_does_not_change_any_task(self):
        self.client.force_authenticate(user=self.member)

        first = self.create_task(
            title="First",
            status=Task.Status.TODO,
            position=0,
        )
        second = self.create_task(
            title="Second",
            status=Task.Status.TODO,
            position=1,
        )
        destination = self.create_task(
            title="Destination",
            status=Task.Status.IN_PROGRESS,
            position=0,
        )

        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": second.pk,
            },
        )

        before = list(
            Task.objects.filter(
                project=self.project,
            )
            .order_by("pk")
            .values_list("pk", "status", "position")
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 99,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        after = list(
            Task.objects.filter(
                project=self.project,
            )
            .order_by("pk")
            .values_list("pk", "status", "position")
        )

        self.assertEqual(before, after)

    def test_kanban_positions_remain_contiguous_after_mixed_operations(self):
        self.client.force_authenticate(user=self.owner)

        created_ids = []

        for index in range(4):
            response = self.client.post(
                self.list_url,
                {"title": f"Kanban Task {index}"},
                format="json",
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )
            created_ids.append(response.data["id"])

        # Move the third task to the beginning.
        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": created_ids[2],
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.TODO,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Change the second task's status using PATCH.
        second_task = Task.objects.get(pk=created_ids[1])

        response = self.client.patch(
            self.get_detail_url(second_task),
            {"status": Task.Status.IN_PROGRESS},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Move the fourth task into the progress column.
        move_url = reverse(
            "workspaces_api_v1:tasks_api_v1:task-move",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": created_ids[3],
            },
        )

        response = self.client.post(
            move_url,
            {
                "status": Task.Status.IN_PROGRESS,
                "position": 0,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Delete the first task.
        first_task = Task.objects.get(pk=created_ids[0])

        response = self.client.delete(
            self.get_detail_url(first_task),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        # Verify all remaining columns have contiguous positions.
        for task_status in Task.Status.values:
            positions = list(
                Task.objects.filter(
                    project=self.project,
                    status=task_status,
                )
                .order_by("position", "pk")
                .values_list("position", flat=True)
            )

            self.assertEqual(
                positions,
                list(range(len(positions))),
                msg=f"Invalid positions for {task_status}",
            )

        self.assertEqual(
            Task.objects.filter(project=self.project).count(),
            3,
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

    def test_task_list_orders_status_by_workflow(self):
        self.create_task(
            title="Done task",
            status=Task.Status.DONE,
        )
        self.create_task(
            title="Review task",
            status=Task.Status.IN_REVIEW,
        )
        self.create_task(
            title="Todo task",
            status=Task.Status.TODO,
        )
        self.create_task(
            title="Progress task",
            status=Task.Status.IN_PROGRESS,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"ordering": "status"},
        )

        self.assertEqual(response.status_code, 200)

        actual_statuses = [
            task["status"]
            for task in response.data["results"]
        ]

        self.assertEqual(
            actual_statuses,
            [
                Task.Status.TODO,
                Task.Status.IN_PROGRESS,
                Task.Status.IN_REVIEW,
                Task.Status.DONE,
            ],
        )

    def test_task_list_orders_status_by_reverse_workflow(self):
        self.create_task(
            title="Todo task",
            status=Task.Status.TODO,
        )
        self.create_task(
            title="Review task",
            status=Task.Status.IN_REVIEW,
        )
        self.create_task(
            title="Done task",
            status=Task.Status.DONE,
        )
        self.create_task(
            title="Progress task",
            status=Task.Status.IN_PROGRESS,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"ordering": "-status"},
        )

        self.assertEqual(response.status_code, 200)

        actual_statuses = [
            task["status"]
            for task in response.data["results"]
        ]

        self.assertEqual(
            actual_statuses,
            [
                Task.Status.DONE,
                Task.Status.IN_REVIEW,
                Task.Status.IN_PROGRESS,
                Task.Status.TODO,
            ],
        )

    def test_task_list_orders_due_date_ascending_nulls_last(self):
        self.create_task(
            title="No due date",
            due_date=None,
        )
        self.create_task(
            title="Later due date",
            due_date=date(2027, 3, 20),
        )
        self.create_task(
            title="Earlier due date",
            due_date=date(2027, 1, 10),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"ordering": "due_date"},
        )

        self.assertEqual(response.status_code, 200)

        actual_titles = [
            task["title"]
            for task in response.data["results"]
        ]

        self.assertEqual(
            actual_titles,
            [
                "Earlier due date",
                "Later due date",
                "No due date",
            ],
        )

    def test_task_list_orders_due_date_descending_nulls_last(self):
        self.create_task(
            title="No due date",
            due_date=None,
        )
        self.create_task(
            title="Earlier due date",
            due_date=date(2027, 1, 10),
        )
        self.create_task(
            title="Later due date",
            due_date=date(2027, 3, 20),
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"ordering": "-due_date"},
        )

        self.assertEqual(response.status_code, 200)

        actual_titles = [
            task["title"]
            for task in response.data["results"]
        ]

        self.assertEqual(
            actual_titles,
            [
                "Later due date",
                "Earlier due date",
                "No due date",
            ],
        )

    def test_task_list_filters_multiple_statuses(self):
        self.create_task(
            title="Todo task",
            status=Task.Status.TODO,
        )
        self.create_task(
            title="Progress task",
            status=Task.Status.IN_PROGRESS,
        )
        self.create_task(
            title="Done task",
            status=Task.Status.DONE,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"status": "todo,done"},
        )

        self.assertEqual(response.status_code, 200)

        actual_statuses = {
            task["status"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_statuses,
            {
                Task.Status.TODO,
                Task.Status.DONE,
            },
        )
        self.assertEqual(response.data["count"], 2)

    def test_task_list_multi_status_edge_cases(self):
        self.create_task(
            title="Todo task",
            status=Task.Status.TODO,
        )
        self.create_task(
            title="Done task",
            status=Task.Status.DONE,
        )

        self.client.force_authenticate(user=self.owner)

        valid_cases = [
            ("todo", 1),
            ("todo,done", 2),
            ("todo, done", 2),
            ("todo,todo", 1),
        ]

        for value, expected_count in valid_cases:
            with self.subTest(status=value):
                response = self.client.get(
                    self.list_url,
                    {"status": value},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.data["count"],
                    expected_count,
                )

        invalid_cases = [
            "",
            "invalid",
            "todo,invalid",
            "todo,",
            ",done",
            "todo,,done",
        ]

        for value in invalid_cases:
            with self.subTest(status=value):
                response = self.client.get(
                    self.list_url,
                    {"status": value},
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("status", response.data)

    def test_task_list_filters_due_before(self):
        self.create_task(
            title="Earlier task",
            due_date=date(2027, 1, 10),
        )
        self.create_task(
            title="Boundary task",
            due_date=date(2027, 3, 20),
        )
        self.create_task(
            title="Later task",
            due_date=date(2027, 5, 10),
        )
        self.create_task(
            title="No due date",
            due_date=None,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"due_before": "2027-03-20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        actual_titles = {
            task["title"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_titles,
            {"Earlier task"},
        )

    def test_task_list_rejects_invalid_due_before(self):
        self.create_task(
            title="Example task",
            due_date=date(2027, 1, 10),
        )

        self.client.force_authenticate(user=self.owner)

        invalid_dates = [
            "",
            "invalid",
            "2027-13-01",
            "2027-02-30",
            "20-03-2027",
            "2027-03-20T12:00:00",
        ]

        for value in invalid_dates:
            with self.subTest(due_before=value):
                response = self.client.get(
                    self.list_url,
                    {"due_before": value},
                )

                self.assertEqual(
                    response.status_code,
                    400,
                )
                self.assertIn(
                    "due_before",
                    response.data,
                )

    def test_task_list_combines_status_and_due_before(self):
        self.create_task(
            title="Matching todo",
            status=Task.Status.TODO,
            due_date=date(2027, 1, 10),
        )
        self.create_task(
            title="Matching done",
            status=Task.Status.DONE,
            due_date=date(2027, 2, 15),
        )
        self.create_task(
            title="Wrong status",
            status=Task.Status.IN_PROGRESS,
            due_date=date(2027, 1, 10),
        )
        self.create_task(
            title="Wrong date",
            status=Task.Status.TODO,
            due_date=date(2027, 5, 10),
        )
        self.create_task(
            title="No due date",
            status=Task.Status.DONE,
            due_date=None,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "status": "todo,done",
                "due_before": "2027-03-20",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        actual_titles = {
            task["title"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_titles,
            {
                "Matching todo",
                "Matching done",
            },
        )

    def test_task_list_filters_overdue_tasks(self):
        from unittest.mock import patch

        self.create_task(
            title="Overdue todo",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="Overdue progress",
            status=Task.Status.IN_PROGRESS,
            due_date=date(2026, 11, 2),
        )
        self.create_task(
            title="Due today",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 3),
        )
        self.create_task(
            title="Completed task",
            status=Task.Status.DONE,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="No due date",
            status=Task.Status.TODO,
            due_date=None,
        )

        self.client.force_authenticate(user=self.owner)

        with patch(
            "tasks.api.v1.views.timezone.localdate",
            return_value=date(2026, 11, 3),
        ):
            response = self.client.get(
                self.list_url,
                {"overdue": "true"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        actual_titles = {
            task["title"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_titles,
            {
                "Overdue todo",
                "Overdue progress",
            },
        )

    def test_task_list_overdue_parameter_edge_cases(self):
        from unittest.mock import patch

        self.create_task(
            title="Overdue task",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="Future task",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 10),
        )

        self.create_task(
            title="Completed task",
            status=Task.Status.DONE,
            due_date=date(2026, 11, 1),
        )

        self.client.force_authenticate(user=self.owner)

        valid_cases = [
            ("true", 1),
            ("TRUE", 1),
            ("false", 3),
            ("FALSE", 3),
        ]

        invalid_cases = [
            "",
            "invalid",
            "yes",
            "1",
            "null",
        ]

        with patch(
            "tasks.api.v1.views.timezone.localdate",
            return_value=date(2026, 11, 3),
        ):
            for value, expected_count in valid_cases:
                with self.subTest(overdue=value):
                    response = self.client.get(
                        self.list_url,
                        {"overdue": value},
                    )

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        response.data["count"],
                        expected_count,
                    )

            for value in invalid_cases:
                with self.subTest(overdue=value):
                    response = self.client.get(
                        self.list_url,
                        {"overdue": value},
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertIn("overdue", response.data)

    def test_task_list_combines_overdue_and_status(self):
        from unittest.mock import patch

        self.create_task(
            title="Overdue todo",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="Overdue progress",
            status=Task.Status.IN_PROGRESS,
            due_date=date(2026, 11, 2),
        )
        self.create_task(
            title="Overdue review",
            status=Task.Status.IN_REVIEW,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="Completed overdue",
            status=Task.Status.DONE,
            due_date=date(2026, 11, 1),
        )
        self.create_task(
            title="Future todo",
            status=Task.Status.TODO,
            due_date=date(2026, 11, 10),
        )

        self.client.force_authenticate(user=self.owner)

        with patch(
            "tasks.api.v1.views.timezone.localdate",
            return_value=date(2026, 11, 3),
        ):
            response = self.client.get(
                self.list_url,
                {
                    "overdue": "true",
                    "status": "todo,in_progress",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        actual_titles = {
            task["title"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_titles,
            {
                "Overdue todo",
                "Overdue progress",
            },
        )

    def test_task_list_filters_assignee_me(self):
        self.create_task(
            title="Assigned to me",
            assignee=self.owner,
        )
        self.create_task(
            title="Assigned to another user",
            assignee=self.member,
        )
        self.create_task(
            title="Unassigned task",
            assignee=None,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"assignee": "me"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        actual_titles = {
            task["title"]
            for task in response.data["results"]
        }

        self.assertEqual(
            actual_titles,
            {"Assigned to me"},
        )

    def test_task_list_assignee_filter_backward_compatibility(self):
        self.create_task(
            title="Owner task",
            assignee=self.owner,
        )
        self.create_task(
            title="Member task",
            assignee=self.member,
        )
        self.create_task(
            title="Unassigned task",
            assignee=None,
        )

        self.client.force_authenticate(user=self.owner)

        valid_cases = [
            (str(self.owner.pk), {"Owner task"}),
            (str(self.member.pk), {"Member task"}),
            ("me", {"Owner task"}),
        ]

        for value, expected_titles in valid_cases:
            with self.subTest(assignee=value):
                response = self.client.get(
                    self.list_url,
                    {"assignee": value},
                )

                self.assertEqual(response.status_code, 200)

                actual_titles = {
                    task["title"]
                    for task in response.data["results"]
                }

                self.assertEqual(
                    actual_titles,
                    expected_titles,
                )
                self.assertEqual(
                    response.data["count"],
                    len(expected_titles),
                )

    def test_task_list_rejects_assignee_me_with_unassigned(self):
        self.create_task(
            title="Assigned task",
            assignee=self.owner,
        )
        self.create_task(
            title="Unassigned task",
            assignee=None,
        )

        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "assignee": "me",
                "unassigned": "true",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            "assignee" in response.data
            or "unassigned" in response.data
        )

    def test_task_list_rejects_invalid_assignee_values(self):
        self.create_task(
            title="Owner task",
            assignee=self.owner,
        )

        self.client.force_authenticate(user=self.owner)

        invalid_values = [
            "",
            "invalid",
            "ME",
            "me,123",
            "1.5",
        ]

        for value in invalid_values:
            with self.subTest(assignee=value):
                response = self.client.get(
                    self.list_url,
                    {"assignee": value},
                )

                self.assertEqual(
                    response.status_code,
                    400,
                )
                self.assertIn(
                    "assignee",
                    response.data,
                )

    def test_task_list_assignee_me_uses_authenticated_user(self):
        self.create_task(
            title="Owner task",
            assignee=self.owner,
        )
        self.create_task(
            title="Member task",
            assignee=self.member,
        )

        cases = [
            (self.owner, "Owner task"),
            (self.member, "Member task"),
        ]

        for user, expected_title in cases:
            with self.subTest(user=user.pk):
                self.client.force_authenticate(user=user)

                response = self.client.get(
                    self.list_url,
                    {"assignee": "me"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["title"],
                    expected_title,
                )
