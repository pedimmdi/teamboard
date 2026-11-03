from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task
from tasks.services import move_task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class TaskMoveConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest(
                "This test requires PostgreSQL row-level locks."
            )

        self.user = User.objects.create_user(
            email="kanban-concurrency@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Concurrency Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        with transaction.atomic():
            self.project = Project.objects.create(
                workspace=self.workspace,
                name="Concurrency Project",
                created_by=self.user,
            )

            ProjectMembership.objects.create(
                project=self.project,
                user=self.user,
                role=ProjectMembership.Role.MANAGER,
            )

        self.tasks = [
            Task.objects.create(
                project=self.project,
                title=f"Task {index}",
                created_by=self.user,
                status=Task.Status.TODO,
                position=index,
            )
            for index in range(4)
        ]

    def test_concurrent_moves_preserve_unique_contiguous_positions(self):
        barrier = Barrier(2, timeout=15)

        def perform_move(task_id):
            connections.close_all()

            try:
                task = Task.objects.get(pk=task_id)
                actor = User.objects.get(pk=self.user.pk)

                barrier.wait()

                return move_task(
                    task=task,
                    actor=actor,
                    status=Task.Status.TODO,
                    position=0,
                ).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(perform_move, self.tasks[2].pk),
                executor.submit(perform_move, self.tasks[3].pk),
            ]

            moved_ids = [
                future.result(timeout=30)
                for future in futures
            ]

        self.assertEqual(
            set(moved_ids),
            {
                self.tasks[2].pk,
                self.tasks[3].pk,
            },
        )

        ordered_tasks = list(
            Task.objects.filter(
                project=self.project,
                status=Task.Status.TODO,
            ).order_by("position", "pk")
        )

        self.assertEqual(
            [task.position for task in ordered_tasks],
            [0, 1, 2, 3],
        )

        self.assertEqual(
            {task.pk for task in ordered_tasks},
            {task.pk for task in self.tasks},
        )

        self.assertIn(
            ordered_tasks[0].pk,
            {
                self.tasks[2].pk,
                self.tasks[3].pk,
            },
        )
