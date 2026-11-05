from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework.exceptions import ValidationError

from projects.services import create_project
from tasks.models import Task
from tasks.services import create_task, move_task
from workspaces.models import Workspace, WorkspaceMembership


class TaskMoveTargetTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="move-target@example.com")
        self.workspace = Workspace.objects.create(name="Move targets")
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.project = create_project(workspace=self.workspace, created_by=self.user, name="Project")
        self.tasks = [create_task(project=self.project, actor=self.user, title=str(index)) for index in range(3)]
        self.client.force_authenticate(self.user)

    def url(self, task):
        return f"/api/v1/workspaces/{self.workspace.slug}/projects/{self.project.pk}/tasks/{task.pk}/move/"

    def order(self, status="todo"):
        return list(Task.objects.filter(project=self.project, status=status).order_by("position").values_list("pk", flat=True))

    def test_anchor_reorders_within_column(self):
        response = self.client.post(self.url(self.tasks[2]), {"status": "todo", "before_task": str(self.tasks[1].pk)}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order(), [self.tasks[0].pk, self.tasks[2].pk, self.tasks[1].pk])

    def test_anchor_moves_across_columns_and_compacts_source(self):
        target = create_task(project=self.project, actor=self.user, title="Target", status="done")
        response = self.client.post(self.url(self.tasks[1]), {"status": "done", "before_task": str(target.pk)}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order("done"), [self.tasks[1].pk, target.pk])
        self.assertEqual(list(Task.objects.filter(project=self.project, status="todo").order_by("position").values_list("position", flat=True)), [0, 1])

    def test_column_placements_use_current_column_boundaries(self):
        for placement, expected in (("first", [2, 0, 1]), ("last", [0, 1, 2])):
            with self.subTest(placement=placement):
                response = self.client.post(self.url(self.tasks[2]), {"status": "todo", "placement": placement}, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.order(), [self.tasks[index].pk for index in expected])
        response = self.client.post(self.url(self.tasks[2]), {"status": "in_review", "placement": "last"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["position"], 0)

    def test_invalid_or_ambiguous_targets_leave_tasks_unchanged(self):
        payloads = [
            {}, {"position": 0, "placement": "last"},
            {"before_task": str(self.tasks[1].pk), "position": 0},
            {"before_task": str(self.tasks[1].pk), "placement": "first"},
            {"before_task": str(self.tasks[0].pk)},
            {"before_task": "invalid"}, {"before_task": None},
            {"placement": "middle"}, {"position": -1},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.url(self.tasks[0]), {"status": "todo", **payload}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.order(), [task.pk for task in self.tasks])

    def test_missing_and_other_project_anchors_are_not_disclosed(self):
        other = create_project(workspace=self.workspace, created_by=self.user, name="Other")
        target = create_task(project=other, actor=self.user, title="Other task")
        for task_id in (uuid4(), target.pk):
            with self.subTest(task_id=task_id):
                response = self.client.post(self.url(self.tasks[0]), {"status": "todo", "before_task": str(task_id)}, format="json")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(self.order(), [task.pk for task in self.tasks])

    def test_anchor_moved_to_another_column_is_rejected_without_mutation(self):
        move_task(task=self.tasks[1], actor=self.user, status="done", placement="last")
        response = self.client.post(self.url(self.tasks[0]), {"status": "todo", "before_task": str(self.tasks[1].pk)}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("before_task", response.data)
        self.assertEqual(self.order(), [self.tasks[0].pk, self.tasks[2].pk])

    def test_stale_task_instances_do_not_determine_anchor_positions(self):
        stale_anchor = self.tasks[1]
        move_task(task=stale_anchor, actor=self.user, status="todo", placement="last")
        result = move_task(task=self.tasks[0], actor=self.user, status="todo", before_task=stale_anchor.pk)
        self.assertEqual(result.position, 1)
        self.assertEqual(self.order(), [self.tasks[2].pk, self.tasks[0].pk, stale_anchor.pk])

    def test_direct_service_calls_validate_selectors(self):
        for target in ({}, {"position": True}, {"before_task": "invalid"}, {"placement": "middle"}, {"position": 0, "placement": "first"}):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                move_task(task=self.tasks[0], actor=self.user, status="todo", **target)
