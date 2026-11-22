from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from projects.models import Project, ProjectMembership
from tasks.models import Task, TaskReminder
from workspaces.models import Workspace, WorkspaceMembership
from calendars.models import CalendarEvent
from notifications.models import Notification


User = get_user_model()


class WorkspaceDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="dashboard-owner@example.com",
        )
        cls.member = User.objects.create_user(
            email="dashboard-member@example.com",
        )
        cls.outsider = User.objects.create_user(
            email="dashboard-outsider@example.com",
        )

        cls.workspace = Workspace.objects.create(
            name="Dashboard Workspace",
        )
        cls.second_workspace = Workspace.objects.create(
            name="Second Workspace",
        )

        for workspace in (cls.workspace, cls.second_workspace):
            for user, role in (
                (cls.owner, WorkspaceMembership.Role.OWNER),
                (cls.member, WorkspaceMembership.Role.MEMBER),
            ):
                WorkspaceMembership.objects.create(
                    workspace=workspace,
                    user=user,
                    role=role,
                )

        cls.project = Project.objects.create(
            workspace=cls.workspace,
            name="Visible Project",
            created_by=cls.owner,
        )
        cls.hidden_project = Project.objects.create(
            workspace=cls.workspace,
            name="Hidden Project",
            created_by=cls.owner,
        )
        cls.second_project = Project.objects.create(
            workspace=cls.second_workspace,
            name="Second Project",
            created_by=cls.owner,
        )

        for project in (
            cls.project,
            cls.hidden_project,
            cls.second_project,
        ):
            ProjectMembership.objects.create(
                project=project,
                user=cls.owner,
                role=ProjectMembership.Role.MANAGER,
            )
            ProjectMembership.objects.create(
                project=project,
                user=cls.member,
                role=ProjectMembership.Role.MEMBER,
            )

        cls.assigned = Task.objects.create(
            project=cls.project,
            title="Assigned to me",
            created_by=cls.owner,
            assignee=cls.member,
            due_date=date.today() + timedelta(days=1),
        )

        cls.self_task = Task.objects.create(
            project=cls.project,
            title="My own task",
            created_by=cls.member,
            assignee=cls.member,
            status=Task.Status.IN_PROGRESS,
        )

        cls.follow_up = Task.objects.create(
            project=cls.project,
            title="Follow up with owner",
            created_by=cls.member,
            assignee=cls.owner,
        )

        cls.completed = Task.objects.create(
            project=cls.project,
            title="Completed follow up",
            created_by=cls.member,
            assignee=cls.owner,
            status=Task.Status.DONE,
        )

        cls.hidden = Task.objects.create(
            project=cls.hidden_project,
            title="Formerly accessible task",
            created_by=cls.member,
            assignee=cls.owner,
        )

        # The creator later loses access to this project.
        ProjectMembership.objects.filter(
            project=cls.hidden_project,
            user=cls.member,
        ).delete()

        cls.second_task = Task.objects.create(
            project=cls.second_project,
            title="Task in another workspace",
            created_by=cls.member,
            assignee=cls.owner,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.member)

        self.url = reverse(
            "workspaces_api_v1:dashboard_api_v1:overview",
            kwargs={"slug": self.workspace.slug},
        )

        self.second_url = reverse(
            "workspaces_api_v1:dashboard_api_v1:overview",
            kwargs={"slug": self.second_workspace.slug},
        )

    def test_today_task_count(self):
        Task.objects.create(project=self.project, assignee=self.member, title="Due today", due_date=timezone.localdate())
        expected_today = Task.objects.filter(project=self.project, assignee=self.member, due_date=timezone.localdate()).exclude(status="done").count()
        response = self.client.get(self.url)
        self.assertEqual(response.data["today_tasks_count"], expected_today)

    def test_my_tasks_and_follow_up_are_correct(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["my_tasks"]["count"], 2)
        self.assertEqual(response.data["follow_up"]["count"], 1)

        my_ids = {
            row["id"]
            for row in response.data["my_tasks"]["items"]
        }
        follow_up_ids = {
            row["id"]
            for row in response.data["follow_up"]["items"]
        }

        self.assertEqual(
            my_ids,
            {str(self.assigned.pk), str(self.self_task.pk)},
        )
        self.assertEqual(
            follow_up_ids,
            {str(self.follow_up.pk)},
        )

    def test_switching_workspace_changes_dashboard_data(self):
        response = self.client.get(self.second_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["my_tasks"]["count"], 0)
        self.assertEqual(response.data["follow_up"]["count"], 1)
        self.assertEqual(
            response.data["follow_up"]["items"][0]["id"],
            str(self.second_task.pk),
        )

    def test_project_permissions_are_enforced(self):
        response = self.client.get(self.url)

        all_ids = {
            row["id"]
            for key in ("my_tasks", "follow_up")
            for row in response.data[key]["items"]
        }

        self.assertNotIn(str(self.hidden.pk), all_ids)
        self.assertNotIn(str(self.second_task.pk), all_ids)
        self.assertNotIn(str(self.completed.pk), all_ids)

    def test_workspace_owner_can_see_accessible_private_project(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["my_tasks"]["count"], 2)

        ids = {
            row["id"]
            for row in response.data["my_tasks"]["items"]
        }

        self.assertIn(str(self.hidden.pk), ids)

    def test_outsider_and_anonymous_user_are_denied(self):
        self.client.force_authenticate(user=self.outsider)

        self.assertEqual(
            self.client.get(self.url).status_code,
            404,
        )

        self.client.force_authenticate(user=None)

        self.assertEqual(
            self.client.get(self.url).status_code,
            401,
        )

    def test_workspace_access_revocation_is_enforced(self):
        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_dashboard_is_read_only(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 405)

    def test_preview_is_limited_but_count_is_complete(self):
        for number in range(6):
            Task.objects.create(
                project=self.project,
                title=f"Extra task {number}",
                created_by=self.owner,
                assignee=self.member,
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["my_tasks"]["count"], 8)
        self.assertEqual(
            len(response.data["my_tasks"]["items"]),
            5,
        )

    def test_member_without_projects_gets_empty_sections(self):
        user = User.objects.create_user(
            email="dashboard-empty@example.com",
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=user,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["my_tasks"]["count"], 0)
        self.assertEqual(response.data["follow_up"]["count"], 0)

    def test_new_sections_have_correct_initial_counts(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["overdue_tasks"]["count"], 0
        )
        self.assertEqual(
            response.data["due_soon_tasks"]["count"], 1
        )
        self.assertEqual(
            response.data["completed_tasks"]["count"], 0
        )
        self.assertEqual(
            response.data["projects"]["count"], 1
        )

        self.assertEqual(
            response.data["as_of"],
            timezone.localdate().isoformat(),
        )
        self.assertEqual(
            response.data["due_soon_until"],
            (
                timezone.localdate() + timedelta(days=7)
            ).isoformat(),
        )

    def test_deadline_boundaries_and_completed_tasks(self):
        today = timezone.localdate()

        def make_task(title, due_date, status=Task.Status.TODO):
            return Task.objects.create(
                project=self.project,
                title=title,
                created_by=self.owner,
                assignee=self.member,
                due_date=due_date,
                status=status,
            )

        overdue = make_task(
            "Overdue",
            today - timedelta(days=1),
        )
        due_today = make_task("Due today", today)
        due_last_day = make_task(
            "Due in seven days",
            today + timedelta(days=7),
        )
        make_task(
            "Outside due soon",
            today + timedelta(days=8),
        )
        completed = make_task(
            "Completed overdue task",
            today - timedelta(days=2),
            Task.Status.DONE,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        # Existing assigned task is due tomorrow.
        self.assertEqual(
            response.data["due_soon_tasks"]["count"], 3
        )
        self.assertEqual(
            response.data["overdue_tasks"]["count"], 1
        )
        self.assertEqual(
            response.data["completed_tasks"]["count"], 1
        )

        overdue_ids = {
            row["id"]
            for row in response.data["overdue_tasks"]["items"]
        }
        due_soon_ids = {
            row["id"]
            for row in response.data["due_soon_tasks"]["items"]
        }
        completed_ids = {
            row["id"]
            for row in response.data["completed_tasks"]["items"]
        }

        self.assertEqual(overdue_ids, {str(overdue.pk)})
        self.assertIn(str(due_today.pk), due_soon_ids)
        self.assertIn(str(due_last_day.pk), due_soon_ids)
        self.assertEqual(completed_ids, {str(completed.pk)})

    def test_follow_up_overdue_is_not_my_overdue(self):
        today = timezone.localdate()

        follow_up = Task.objects.create(
            project=self.project,
            title="Another user's overdue assignment",
            created_by=self.member,
            assignee=self.owner,
            due_date=today - timedelta(days=3),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["overdue_tasks"]["count"], 0
        )
        self.assertEqual(
            response.data["follow_up"]["count"], 2
        )

        follow_up_ids = {
            row["id"]
            for row in response.data["follow_up"]["items"]
        }
        self.assertIn(str(follow_up.pk), follow_up_ids)

    def test_project_visibility_follows_workspace_roles(self):
        member_response = self.client.get(self.url)

        self.assertEqual(
            member_response.data["projects"]["count"], 1
        )
        self.assertEqual(
            member_response.data["projects"]["items"][0]["id"],
            str(self.project.pk),
        )

        self.client.force_authenticate(user=self.owner)

        owner_response = self.client.get(self.url)

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(
            owner_response.data["projects"]["count"], 2
        )

        project_ids = {
            row["id"]
            for row in owner_response.data["projects"]["items"]
        }

        self.assertIn(str(self.project.pk), project_ids)
        self.assertIn(str(self.hidden_project.pk), project_ids)
        self.assertNotIn(str(self.second_project.pk), project_ids)

    def test_due_soon_preview_has_five_items(self):
        today = timezone.localdate()

        for index in range(6):
            Task.objects.create(
                project=self.project,
                title=f"Upcoming task {index}",
                created_by=self.owner,
                assignee=self.member,
                due_date=today + timedelta(days=index),
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        # Six new tasks and the existing task due tomorrow.
        self.assertEqual(
            response.data["due_soon_tasks"]["count"], 7
        )
        self.assertEqual(
            len(response.data["due_soon_tasks"]["items"]), 5
        )

    def test_upcoming_reminders_are_private_and_scoped(self):
        now = timezone.now()

        def make_reminder(task, recipient, moment, **kwargs):
            return TaskReminder.objects.create(
                task=task,
                recipient=recipient,
                kind=TaskReminder.Kind.ABSOLUTE,
                timezone="UTC",
                run_at=moment,
                **kwargs,
            )

        visible = make_reminder(
            self.assigned,
            self.member,
            now + timedelta(hours=2),
        )

        # Another user's private reminder.
        make_reminder(
            self.assigned,
            self.owner,
            now + timedelta(hours=3),
        )

        # A project this member can no longer access.
        make_reminder(
            self.hidden,
            self.member,
            now + timedelta(hours=4),
        )

        # Another workspace.
        make_reminder(
            self.second_task,
            self.member,
            now + timedelta(hours=5),
        )

        # Already overdue.
        make_reminder(
            self.assigned,
            self.member,
            now - timedelta(hours=1),
        )

        # A reminder awaiting due-date recalculation.
        make_reminder(
            self.assigned,
            self.member,
            now + timedelta(hours=6),
            needs_recalculation=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        section = response.data["upcoming_reminders"]
        self.assertEqual(section["count"], 1)
        self.assertEqual(len(section["items"]), 1)

        item = section["items"][0]

        self.assertEqual(str(item["id"]), str(visible.pk))
        self.assertEqual(str(item["task"]), str(self.assigned.pk))
        self.assertEqual(str(item["project"]), str(self.project.pk))

    def test_upcoming_events_respect_project_and_time_scope(self):
        now = timezone.now()

        def make_event(project, title, starts_at):
            return CalendarEvent.objects.create(
                project=project,
                title=title,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
            )

        first = make_event(
            self.project,
            "Team meeting",
            now + timedelta(hours=2),
        )

        second = make_event(
            self.project,
            "Sprint planning",
            now + timedelta(days=5),
        )

        make_event(
            self.project,
            "Past event",
            now - timedelta(days=1),
        )

        make_event(
            self.project,
            "Outside window",
            now + timedelta(days=8),
        )

        make_event(
            self.hidden_project,
            "Private project event",
            now + timedelta(days=1),
        )

        make_event(
            self.second_project,
            "Other workspace event",
            now + timedelta(days=1),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        section = response.data["upcoming_events"]

        self.assertEqual(section["count"], 2)

        ids = [str(item["id"]) for item in section["items"]]

        self.assertEqual(
            ids,
            [str(first.pk), str(second.pk)],
        )

        self.assertEqual(
            str(section["items"][0]["project"]),
            str(self.project.pk),
        )

    def test_recent_notifications_are_private_and_scoped(self):
        now = timezone.now()

        def make_notification(task, recipient, **kwargs):
            return Notification.objects.create(
                recipient=recipient,
                event_type=Notification.EventType.TASK_ASSIGNED,
                workspace=task.project.workspace,
                project=task.project,
                task=task,
                **kwargs,
            )

        unread = make_notification(
            self.assigned,
            self.member,
            payload={"private_field": "must-not-leak"},
        )

        read = make_notification(
            self.assigned,
            self.member,
            read_at=now,
        )

        make_notification(
            self.hidden,
            self.member,
        )

        make_notification(
            self.second_task,
            self.member,
        )

        make_notification(
            self.assigned,
            self.owner,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        section = response.data["recent_notifications"]

        self.assertEqual(section["count"], 2)
        self.assertEqual(section["unread_count"], 1)

        ids = {item["id"] for item in section["items"]}

        self.assertEqual(
            ids,
            {str(unread.pk), str(read.pk)},
        )

        unread_item = next(
            item
            for item in section["items"]
            if item["id"] == str(unread.pk)
        )

        # The existing notification serializer must still
        # prevent arbitrary payload fields from leaking.
        self.assertEqual(unread_item["payload"], {})

    def test_new_sections_have_bounded_previews(self):
        now = timezone.now()

        for index in range(6):
            task = Task.objects.create(
                project=self.project,
                title=f"Dashboard preview task {index}",
                created_by=self.owner,
                assignee=self.member,
            )

            TaskReminder.objects.create(
                task=task,
                recipient=self.member,
                kind=TaskReminder.Kind.ABSOLUTE,
                timezone="UTC",
                run_at=now + timedelta(hours=index + 1),
            )

            starts_at = now + timedelta(hours=index + 1)

            CalendarEvent.objects.create(
                project=self.project,
                title=f"Dashboard event {index}",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
            )

            Notification.objects.create(
                recipient=self.member,
                event_type=Notification.EventType.TASK_ASSIGNED,
                workspace=self.workspace,
                project=self.project,
                task=task,
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        for key in (
            "upcoming_reminders",
            "upcoming_events",
            "recent_notifications",
        ):
            with self.subTest(section=key):
                self.assertEqual(response.data[key]["count"], 6)
                self.assertEqual(
                    len(response.data[key]["items"]),
                    5,
                )

        self.assertEqual(
            response.data["recent_notifications"]["unread_count"],
            6,
        )

    def test_revoked_project_access_hides_all_new_sections(self):
        now = timezone.now()

        TaskReminder.objects.create(
            task=self.assigned,
            recipient=self.member,
            kind=TaskReminder.Kind.ABSOLUTE,
            timezone="UTC",
            run_at=now + timedelta(hours=2),
        )

        CalendarEvent.objects.create(
            project=self.project,
            title="Previously accessible event",
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=3),
        )

        Notification.objects.create(
            recipient=self.member,
            event_type=Notification.EventType.TASK_ASSIGNED,
            workspace=self.workspace,
            project=self.project,
            task=self.assigned,
        )

        before = self.client.get(self.url)

        self.assertEqual(
            before.data["upcoming_reminders"]["count"], 1
        )
        self.assertEqual(
            before.data["upcoming_events"]["count"], 1
        )
        self.assertEqual(
            before.data["recent_notifications"]["count"], 1
        )

        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).delete()

        after = self.client.get(self.url)

        self.assertEqual(after.status_code, 200)

        for key in (
            "upcoming_reminders",
            "upcoming_events",
            "recent_notifications",
        ):
            with self.subTest(section=key):
                self.assertEqual(after.data[key]["count"], 0)
                self.assertEqual(after.data[key]["items"], [])

        self.assertEqual(
            after.data["recent_notifications"]["unread_count"],
            0,
        )

    def test_upcoming_reminders_only_include_next_seven_days(self):
        now = timezone.now()

        near = TaskReminder.objects.create(
            task=self.assigned,
            recipient=self.member,
            kind=TaskReminder.Kind.ABSOLUTE,
            timezone="UTC",
            run_at=now + timedelta(days=2),
        )

        TaskReminder.objects.create(
            task=self.assigned,
            recipient=self.member,
            kind=TaskReminder.Kind.ABSOLUTE,
            timezone="UTC",
            run_at=now + timedelta(days=8),
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        section = response.data["upcoming_reminders"]

        self.assertEqual(section["count"], 1)
        self.assertEqual(len(section["items"]), 1)
        self.assertEqual(
            str(section["items"][0]["id"]),
            str(near.pk),
        )
