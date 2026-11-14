
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from notifications.models import Notification
from notifications.services import create_notification


User = get_user_model()


class NotificationServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.recipient = User.objects.create_user(
            email="recipient@example.com",
            password="TestPassword123!",
        )
        cls.actor = User.objects.create_user(
            email="actor@example.com",
            password="TestPassword123!",
        )

    def create(self, **overrides):
        data = {
            "recipient": self.recipient,
            "actor": self.actor,
            "event_type": Notification.EventType.TASK_ASSIGNED,
            "deduplication_key": f"test:{uuid4()}",
            "payload": {"message": "Task assigned"},
        }
        data.update(overrides)
        return create_notification(**data)

    def test_creates_notification(self):
        notification, created = self.create()

        self.assertTrue(created)
        self.assertEqual(notification.recipient, self.recipient)
        self.assertEqual(notification.actor, self.actor)
        self.assertEqual(
            notification.event_type,
            Notification.EventType.TASK_ASSIGNED,
        )
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        self.assertEqual(Notification.objects.count(), 1)

    def test_duplicate_event_is_idempotent(self):
        key = f"event:{uuid4()}"

        first, first_created = self.create(
            deduplication_key=key,
        )
        second, second_created = self.create(
            deduplication_key=key,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_duplicate_key_with_different_payload_is_rejected(self):
        key = f"event:{uuid4()}"

        self.create(
            deduplication_key=key,
            payload={"message": "Original"},
        )

        with self.assertRaises(ValidationError):
            self.create(
                deduplication_key=key,
                payload={"message": "Different"},
            )

        self.assertEqual(Notification.objects.count(), 1)

    def test_duplicate_key_for_different_recipient_is_rejected(self):
        key = f"event:{uuid4()}"
        other = User.objects.create_user(
            email="other@example.com",
        )

        self.create(deduplication_key=key)

        with self.assertRaises(ValidationError):
            self.create(
                deduplication_key=key,
                recipient=other,
            )

        self.assertEqual(Notification.objects.count(), 1)

    def test_self_notification_is_skipped(self):
        notification, created = self.create(
            actor=self.recipient,
        )

        self.assertIsNone(notification)
        self.assertFalse(created)
        self.assertFalse(Notification.objects.exists())

    def test_system_notification_without_actor(self):
        notification, created = self.create(actor=None)

        self.assertTrue(created)
        self.assertIsNone(notification.actor)

    def test_inactive_recipient_is_rejected(self):
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            self.create()

        self.assertFalse(Notification.objects.exists())

    def test_invalid_event_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create(event_type="unknown_event")

        self.assertFalse(Notification.objects.exists())

    def test_missing_deduplication_key_is_rejected(self):
        for key in (None, "", " ", " invalid", "x" * 256):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError):
                    self.create(deduplication_key=key)

        self.assertFalse(Notification.objects.exists())

    def test_invalid_payload_is_rejected(self):
        invalid_payloads = [
            ["not", "an", "object"],
            {"invalid": object()},
            {"number": float("nan")},
            {"message": "x" * 5000},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload_type=type(payload).__name__):
                with self.assertRaises(ValidationError):
                    self.create(payload=payload)

        self.assertFalse(Notification.objects.exists())

    def test_project_requires_workspace(self):
        project = SimpleNamespace(
            pk=uuid4(),
            workspace_id=uuid4(),
        )

        with self.assertRaises(ValidationError):
            self.create(project=project)

    def test_project_must_belong_to_workspace(self):
        workspace = SimpleNamespace(pk=uuid4())
        project = SimpleNamespace(
            pk=uuid4(),
            workspace_id=uuid4(),
        )

        with self.assertRaises(ValidationError):
            self.create(
                workspace=workspace,
                project=project,
            )

    def test_task_requires_project(self):
        task = SimpleNamespace(
            pk=uuid4(),
            project_id=uuid4(),
        )

        with self.assertRaises(ValidationError):
            self.create(task=task)

    def test_task_must_belong_to_project(self):
        workspace = SimpleNamespace(pk=uuid4())
        project = SimpleNamespace(
            pk=uuid4(),
            workspace_id=workspace.pk,
        )
        task = SimpleNamespace(
            pk=uuid4(),
            project_id=uuid4(),
        )

        with self.assertRaises(ValidationError):
            self.create(
                workspace=workspace,
                project=project,
                task=task,
            )

    def test_notification_is_rolled_back_with_transaction(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.create()
                raise RuntimeError("Simulated failure")

        self.assertFalse(Notification.objects.exists())
