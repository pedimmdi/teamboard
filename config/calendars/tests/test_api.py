
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from calendars.models import CalendarEvent
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class CalendarAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="calendar-api-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="calendar-api-member@example.com",
            password="Strong-password-2026!",
        )
        self.workspace_only = User.objects.create_user(
            email="calendar-api-workspace@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="calendar-api-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Calendar API Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
            (self.workspace_only, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Calendar API Project",
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
            2027, 5, 10, 9, 0, tzinfo=timezone.utc
        )
        self.end = self.start + timedelta(hours=1)

        self.list_url = reverse(
            "workspaces_api_v1:calendars_api_v1:calendar-event-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
            },
        )
        self.workspace_url = reverse(
            "workspaces_api_v1:workspace-calendar",
            kwargs={"slug": self.workspace.slug},
        )

    def make_event(self, **kwargs):
        return CalendarEvent.objects.create(
            project=kwargs.pop("project", self.project),
            title=kwargs.pop("title", "Planning"),
            starts_at=kwargs.pop("starts_at", self.start),
            ends_at=kwargs.pop("ends_at", self.end),
            created_by=self.owner,
            **kwargs,
        )

    def detail_url(self, event):
        return reverse(
            "workspaces_api_v1:calendars_api_v1:calendar-event-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": event.project_id,
                "event_id": event.pk,
            },
        )

    def payload(self, **overrides):
        data = {
            "title": "Sprint Planning",
            "starts_at": self.start.isoformat(),
            "ends_at": self.end.isoformat(),
        }
        data.update(overrides)
        return data

    def test_anonymous_cannot_list(self):
        response = self.client.get(self.list_url)
        self.assertIn(response.status_code, (401, 403))

    def test_owner_can_create_event(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["title"], "Sprint Planning")
        self.assertEqual(CalendarEvent.objects.count(), 1)

    def test_member_can_create_event(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_workspace_only_member_cannot_create(self):
        self.client.force_authenticate(user=self.workspace_only)

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_outsider_cannot_list(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 404)

    def test_member_can_list_project_events(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(event.pk)],
        )

    def test_member_can_retrieve_event(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.member)

        response = self.client.get(self.detail_url(event))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(event.pk))

    def test_member_can_update_event(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.member)

        response = self.client.patch(
            self.detail_url(event),
            {"title": "Updated Planning"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        event.refresh_from_db()
        self.assertEqual(event.title, "Updated Planning")

    def test_member_cannot_delete_event(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.member)

        response = self.client.delete(self.detail_url(event))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            CalendarEvent.objects.filter(pk=event.pk).exists()
        )

    def test_owner_can_delete_event(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(self.detail_url(event))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            CalendarEvent.objects.filter(pk=event.pk).exists()
        )

    def test_invalid_time_range_returns_400(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            self.payload(ends_at=self.start.isoformat()),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ends_at", response.data)

    def test_invalid_event_type_returns_400(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            self.payload(event_type="invalid"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_cannot_change_project_via_patch(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.detail_url(event),
            {"project": str(self.project.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        event.refresh_from_db()
        self.assertEqual(event.project_id, self.project.pk)

    def test_date_filter_includes_overlapping_events(self):
        overlapping = self.make_event()
        self.make_event(
            title="Later",
            starts_at=self.start + timedelta(days=3),
            ends_at=self.end + timedelta(days=3),
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "start": (
                    self.start + timedelta(minutes=30)
                ).isoformat(),
                "end": (
                    self.end + timedelta(minutes=30)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(overlapping.pk)],
        )

    def test_invalid_filter_range_returns_400(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "start": self.end.isoformat(),
                "end": self.start.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_workspace_calendar_excludes_private_projects(self):
        visible = self.make_event()

        private_project = Project.objects.create(
            workspace=self.workspace,
            name="Private Calendar Project",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=private_project,
            user=self.owner,
            role=ProjectMembership.Role.MANAGER,
        )
        private_event = self.make_event(
            project=private_project,
            title="Private Meeting",
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.workspace_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(visible.pk)},
        )

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.workspace_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {str(visible.pk), str(private_event.pk)},
        )

    def test_workspace_only_member_sees_no_project_events(self):
        self.make_event()
        self.client.force_authenticate(user=self.workspace_only)

        response = self.client.get(self.workspace_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_outsider_cannot_access_workspace_calendar(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.workspace_url)

        self.assertEqual(response.status_code, 404)

    def test_create_rejects_unknown_fields(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            self.payload(unexpected_field="value"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("unexpected_field", response.data)
        self.assertEqual(CalendarEvent.objects.count(), 0)

    def test_update_rejects_unknown_fields(self):
        event = self.make_event()
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            self.detail_url(event),
            {
                "title": "Changed",
                "project": str(self.project.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("project", response.data)

        event.refresh_from_db()
        self.assertEqual(event.title, "Planning")

    def test_calendar_rejects_range_over_93_days(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "start": self.start.isoformat(),
                "end": (
                    self.start + timedelta(days=94)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date_range", response.data)

    def test_calendar_accepts_93_day_range(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {
                "start": self.start.isoformat(),
                "end": (
                    self.start + timedelta(days=93)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_calendar_rejects_incomplete_date_range(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"start": self.start.isoformat()},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date_range", response.data)

    def test_calendar_rejects_duplicate_filter(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url + "?event_type=event&event_type=meeting"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("event_type", response.data)

    def test_project_calendar_pagination(self):
        self.client.force_authenticate(user=self.owner)

        for index in range(5):
            self.make_event(
                title=f"Event {index}",
                starts_at=self.start + timedelta(hours=index),
                ends_at=self.end + timedelta(hours=index),
            )

        response = self.client.get(
            self.list_url,
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

        second_page = self.client.get(
            self.list_url,
            {"page_size": 2, "page": 2},
        )

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.data["results"]), 2)

        first_ids = {
            item["id"] for item in response.data["results"]
        }
        second_ids = {
            item["id"] for item in second_page.data["results"]
        }

        self.assertFalse(first_ids & second_ids)

    def test_workspace_calendar_pagination(self):
        self.client.force_authenticate(user=self.owner)

        for index in range(4):
            self.make_event(
                title=f"Workspace Event {index}",
                starts_at=self.start + timedelta(hours=index),
                ends_at=self.end + timedelta(hours=index),
            )

        response = self.client.get(
            self.workspace_url,
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)

    def test_calendar_rejects_invalid_page(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            self.list_url,
            {"page": "invalid"},
        )

        self.assertEqual(response.status_code, 404)
