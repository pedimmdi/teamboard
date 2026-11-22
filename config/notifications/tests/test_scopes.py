
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from notifications.models import Notification
from notifications.scopes import (
    PROJECT_EVENTS,
    TASK_EVENTS,
    WORKSPACE_EVENTS,
    validate_notification_scope,
)


class NotificationScopeTests(SimpleTestCase):
    def setUp(self):
        self.workspace = SimpleNamespace(pk=uuid4())

        self.project = SimpleNamespace(
            pk=uuid4(),
            workspace_id=self.workspace.pk,
        )

        self.task = SimpleNamespace(
            pk=uuid4(),
            project_id=self.project.pk,
        )

    def validate(self, event_type, **overrides):
        data = {
            "event_type": event_type,
            "workspace": self.workspace,
            "project": None,
            "task": None,
        }
        data.update(overrides)
        return validate_notification_scope(**data)

    def test_every_event_type_has_scope_contract(self):
        covered_events = (
            WORKSPACE_EVENTS | PROJECT_EVENTS | TASK_EVENTS
        )

        self.assertEqual(
            covered_events,
            set(Notification.EventType.values),
        )

        self.assertFalse(WORKSPACE_EVENTS & PROJECT_EVENTS)
        self.assertFalse(WORKSPACE_EVENTS & TASK_EVENTS)
        self.assertFalse(PROJECT_EVENTS & TASK_EVENTS)

    def test_workspace_events_accept_valid_scope(self):
        for event_type in WORKSPACE_EVENTS:
            with self.subTest(event_type=event_type):
                self.validate(event_type)

    def test_project_events_accept_valid_scope(self):
        for event_type in PROJECT_EVENTS:
            with self.subTest(event_type=event_type):
                self.validate(
                    event_type,
                    project=self.project,
                )

    def test_task_events_accept_valid_scope(self):
        for event_type in TASK_EVENTS:
            with self.subTest(event_type=event_type):
                self.validate(
                    event_type,
                    project=self.project,
                    task=self.task,
                )

    def test_every_event_requires_workspace(self):
        for event_type in Notification.EventType.values:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        workspace=None,
                        project=self.project,
                        task=self.task,
                    )

                self.assertIn(
                    "workspace",
                    context.exception.detail,
                )

    def test_workspace_events_reject_project(self):
        for event_type in WORKSPACE_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        project=self.project,
                    )

                self.assertIn(
                    "project",
                    context.exception.detail,
                )

    def test_workspace_events_reject_task(self):
        for event_type in WORKSPACE_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        task=self.task,
                    )

                self.assertIn(
                    "task",
                    context.exception.detail,
                )

    def test_project_events_require_project(self):
        for event_type in PROJECT_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(event_type)

                self.assertIn(
                    "project",
                    context.exception.detail,
                )

    def test_project_events_reject_task(self):
        for event_type in PROJECT_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        project=self.project,
                        task=self.task,
                    )

                self.assertIn(
                    "task",
                    context.exception.detail,
                )

    def test_task_events_require_project(self):
        for event_type in TASK_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        task=self.task,
                    )

                self.assertIn(
                    "project",
                    context.exception.detail,
                )

    def test_task_events_require_task(self):
        for event_type in TASK_EVENTS:
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError) as context:
                    self.validate(
                        event_type,
                        project=self.project,
                    )

                self.assertIn(
                    "task",
                    context.exception.detail,
                )

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaises(ValidationError) as context:
            self.validate("unknown_event")

        self.assertIn(
            "event_type",
            context.exception.detail,
        )
