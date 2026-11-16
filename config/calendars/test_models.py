from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from calendars.models import CalendarEvent
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class CalendarEventModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="calendar-model@example.com",
            password="Strong-password-2026!",
        )
        self.workspace = Workspace.objects.create(
            name="Calendar Model Workspace",
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Calendar Model Project",
            created_by=self.user,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.Role.OWNER,
        )

        ProjectMembership.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMembership.Role.MANAGER,
        )
        self.start = datetime(
            2027, 3, 10, 9, 0, tzinfo=dt_timezone.utc
        )
        self.end = self.start + timedelta(hours=1)

    def make_event(self, **kwargs):
        return CalendarEvent.objects.create(
            project=self.project,
            title=kwargs.pop("title", "Planning"),
            starts_at=kwargs.pop("starts_at", self.start),
            ends_at=kwargs.pop("ends_at", self.end),
            created_by=self.user,
            **kwargs,
        )

    def test_create_event_defaults(self):
        event = self.make_event()

        self.assertEqual(event.title, "Planning")
        self.assertEqual(
            event.event_type,
            CalendarEvent.EventType.EVENT,
        )
        self.assertFalse(event.all_day)
        self.assertEqual(event.created_by, self.user)
        self.assertEqual(str(event), "Planning")

    def test_end_must_be_after_start(self):
        for end in (
            self.start,
            self.start - timedelta(minutes=1),
        ):
            with self.subTest(end=end):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        self.make_event(ends_at=end)

        self.assertEqual(CalendarEvent.objects.count(), 0)

    def test_invalid_event_type_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_event(event_type="invalid")

    def test_project_deletion_cascades_to_events(self):
        event = self.make_event()
        event_id = event.pk

        self.project.delete()

        self.assertFalse(
            CalendarEvent.objects.filter(pk=event_id).exists()
        )

    def test_creator_deletion_preserves_event(self):
        creator = User.objects.create_user(
            email="calendar-event-creator@example.com",
            password="Strong-password-2026!",
        )

        event = self.make_event()
        event.created_by = creator
        event.save(update_fields=["created_by"])

        event_id = event.pk

        creator.delete()

        event = CalendarEvent.objects.get(pk=event_id)
        self.assertIsNone(event.created_by)
        self.assertEqual(event.project, self.project)

    def test_events_order_by_start_time(self):
        later = self.make_event(
            title="Later",
            starts_at=self.start + timedelta(days=1),
            ends_at=self.end + timedelta(days=1),
        )
        earlier = self.make_event(title="Earlier")

        self.assertEqual(
            list(
                CalendarEvent.objects.values_list(
                    "pk", flat=True
                )
            ),
            [earlier.pk, later.pk],
        )
