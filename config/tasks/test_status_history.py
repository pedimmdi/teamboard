from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task, TaskStatusHistory
from tasks.services import move_task, update_task
from workspaces.models import Workspace, WorkspaceMembership


class TaskHistoryTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="history-owner@example.com")
        workspace = Workspace.objects.create(name="Task history")
        WorkspaceMembership.objects.create(workspace=workspace, user=self.owner, role="owner")
        with transaction.atomic():
            self.project = Project.objects.create(workspace=workspace, created_by=self.owner, name="History")
            ProjectMembership.objects.create(project=self.project, user=self.owner, role="manager")

    def test_migration_does_not_invent_completion_dates_for_existing_tasks(self):
        previous = [("tasks", "0005_backfill_task_positions")]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(previous)
            old_task = executor.loader.project_state(previous).apps.get_model("tasks", "Task")
            task_id = old_task.objects.create(
                project_id=self.project.pk, title="Already complete", status="done",
            ).pk
        finally:
            MigrationExecutor(connection).migrate(latest)

        task = Task.objects.get(pk=task_id)
        self.assertIsNone(task.completed_at)
        self.assertFalse(TaskStatusHistory.objects.filter(task_id=task.pk).exists())
        task = update_task(task=task, actor=self.owner, status="todo")
        task = move_task(task=task, actor=self.owner, status="done", placement="last")
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(TaskStatusHistory.objects.filter(task_id=task.pk, status="done").count(), 1)

    def test_concurrent_update_and_move_record_one_completion(self):
        task = Task.objects.create(project=self.project, title="Race")
        start = Barrier(2)

        def finish(move):
            try:
                start.wait(timeout=15)
                if move:
                    move_task(task=task, actor=self.owner, status="done", placement="last")
                else:
                    update_task(task=task, actor=self.owner, status="done")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(finish, move) for move in (True, False)]
            for future in futures:
                future.result(timeout=30)

        task.refresh_from_db()
        completion = TaskStatusHistory.objects.get(task_id=task.pk, status="done")
        self.assertEqual(task.completed_at, completion.changed_at)
