
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from calendars.access import (
    get_accessible_workspace_events,
    get_calendar_event_or_404,
)
from calendars.models import CalendarEvent
from calendars.services import (
    create_calendar_event,
    update_calendar_event,
    delete_calendar_event,
)
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class CalendarServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="calendar-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="calendar-member@example.com",
            password="Strong-password-2026!",
        )
        self.workspace_only = User.objects.create_user(
            email="calendar-workspace@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="calendar-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Calendar Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
            (
                self.workspace_only,
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
            name="Calendar Project",
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

        self.start = datetime(
            2027, 4, 10, 9, 0, tzinfo=timezone.utc
        )
        self.end = self.start + timedelta(hours=1)

    def make_event(self, *, actor=None, **kwargs):
        return create_calendar_event(
            project=self.project,
            actor=actor or self.owner,
            title=kwargs.pop("title", "Sprint Planning"),
            starts_at=kwargs.pop("starts_at", self.start),
            ends_at=kwargs.pop("ends_at", self.end),
            **kwargs,
        )

    def test_owner_can_create_without_project_membership(self):
        event = self.make_event()

        self.assertEqual(event.project, self.project)
        self.assertEqual(event.created_by, self.owner)

    def test_project_member_can_create(self):
        event = self.make_event(actor=self.member)

        self.assertEqual(event.created_by, self.member)

    def test_workspace_only_member_cannot_create(self):
        with self.assertRaises(Http404):
            self.make_event(actor=self.workspace_only)

    def test_outsider_cannot_create(self):
        with self.assertRaises(Http404):
            self.make_event(actor=self.outsider)

    def test_title_is_trimmed(self):
        event = self.make_event(title="  Sprint Planning  ")

        self.assertEqual(event.title, "Sprint Planning")

    def test_invalid_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_event(title="   ")

    def test_invalid_time_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_event(ends_at=self.start)

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_event(
                starts_at=datetime(2027, 4, 10, 9, 0)
            )

    def test_invalid_event_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_event(event_type="unknown")

    def test_all_day_requires_midnight_utc(self):
        with self.assertRaises(ValidationError):
            self.make_event(all_day=True)

    def test_valid_all_day_event(self):
        start = datetime(
            2027, 4, 10, tzinfo=timezone.utc
        )
        event = self.make_event(
            starts_at=start,
            ends_at=start + timedelta(days=1),
            all_day=True,
        )

        self.assertTrue(event.all_day)

    def test_member_can_update(self):
        event = self.make_event()

        updated = update_calendar_event(
            event=event,
            actor=self.member,
            title="Updated Planning",
        )

        self.assertEqual(updated.title, "Updated Planning")

    def test_update_rejects_invalid_range(self):
        event = self.make_event()

        with self.assertRaises(ValidationError):
            update_calendar_event(
                event=event,
                actor=self.owner,
                ends_at=self.start,
            )

        event.refresh_from_db()
        self.assertEqual(event.ends_at, self.end)

    def test_unauthorized_update_does_not_change_event(self):
        event = self.make_event()

        with self.assertRaises(Http404):
            update_calendar_event(
                event=event,
                actor=self.workspace_only,
                title="Unauthorized",
            )

        event.refresh_from_db()
        self.assertEqual(event.title, "Sprint Planning")

    def test_member_cannot_delete(self):
        event = self.make_event()

        with self.assertRaises(PermissionDenied):
            delete_calendar_event(
                event=event,
                actor=self.member,
            )

        self.assertTrue(
            CalendarEvent.objects.filter(pk=event.pk).exists()
        )

    def test_owner_can_delete(self):
        event = self.make_event()

        delete_calendar_event(
            event=event,
            actor=self.owner,
        )

        self.assertFalse(
            CalendarEvent.objects.filter(pk=event.pk).exists()
        )

    def test_event_access_requires_project_membership(self):
        event = self.make_event()

        with self.assertRaises(Http404):
            get_calendar_event_or_404(
                workspace_slug=self.workspace.slug,
                project_id=self.project.pk,
                event_id=event.pk,
                user=self.workspace_only,
            )

    def test_workspace_calendar_filters_private_projects(self):
        visible = self.make_event()

        private_project = Project.objects.create(
            workspace=self.workspace,
            name="Private Project",
            created_by=self.owner,
        )

        ProjectMembership.objects.create(
            project=private_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )

        private_event = create_calendar_event(
            project=private_project,
            actor=self.owner,
            title="Private Meeting",
            starts_at=self.start,
            ends_at=self.end,
        )

        member_ids = set(
            get_accessible_workspace_events(
                workspace_slug=self.workspace.slug,
                user=self.member,
            ).values_list("pk", flat=True)
        )

        owner_ids = set(
            get_accessible_workspace_events(
                workspace_slug=self.workspace.slug,
                user=self.owner,
            ).values_list("pk", flat=True)
        )

        self.assertEqual(member_ids, {visible.pk})
        self.assertEqual(
            owner_ids,
            {visible.pk, private_event.pk},
        )

    def test_outsider_cannot_access_workspace_calendar(self):
        with self.assertRaises(Http404):
            list(
                get_accessible_workspace_events(
                    workspace_slug=self.workspace.slug,
                    user=self.outsider,
                )
            )
