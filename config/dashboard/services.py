
from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from calendars.models import CalendarEvent
from notifications.access import get_accessible_notifications
from projects.access import get_accessible_workspace_project_ids
from projects.models import Project
from tasks.models import Task, TaskReminder


PREVIEW_LIMIT = 5
UPCOMING_DAYS = 7

ACTIVE_STATUSES = (
    Task.Status.TODO,
    Task.Status.IN_PROGRESS,
    Task.Status.IN_REVIEW,
)


def _task_section(queryset, count, *, completed=False):
    """Return an exact count and a bounded task preview."""

    if completed:
        ordering = ("-completed_at", "-updated_at", "pk")
    else:
        ordering = (
            F("due_date").asc(nulls_last=True),
            "-created_at",
            "pk",
        )

    items = list(
        queryset
        .select_related("project", "assignee")
        .order_by(*ordering)[:PREVIEW_LIMIT]
    )

    return {
        "count": count,
        "items": items,
    }


def _project_section(queryset):
    """Return accessible projects with a bounded preview."""

    return {
        "count": queryset.count(),
        "items": list(
            queryset
            .order_by("name", "pk")
            .values("id", "name")[:PREVIEW_LIMIT]
        ),
    }



def _reminder_section(*, project_ids, user, now, until):
    """
    Upcoming private reminders within the next seven days.

    Exclude cancelled, delivered, invalid, disabled,
    failed, and reminders awaiting recalculation.
    """

    reminders = TaskReminder.objects.filter(
        recipient_id=user.pk,
        task__project_id__in=project_ids,
        task__status__in=ACTIVE_STATUSES,
        status=TaskReminder.Status.PENDING,
        needs_recalculation=False,
        run_at__gte=now,
        run_at__lt=until,
    )

    return {
        "count": reminders.count(),
        "items": list(
            reminders
            .select_related("task", "task__project")
            .order_by("run_at", "pk")[:PREVIEW_LIMIT]
        ),
    }


def _calendar_section(*, project_ids, now, until):
    """
    Calendar events starting within the next seven days
    in projects accessible to the current user.
    """

    events = CalendarEvent.objects.filter(
        project_id__in=project_ids,
        starts_at__gte=now,
        starts_at__lt=until,
    )

    return {
        "count": events.count(),
        "items": list(
            events
            .select_related("project")
            .order_by("starts_at", "pk")[:PREVIEW_LIMIT]
        ),
    }


def _notification_section(*, workspace, user):
    """
    Reuse the existing notification visibility policy.

    Do not access Notification.objects directly because
    the inbox has additional project/scope permissions.
    """

    notifications = get_accessible_notifications(user).filter(
        workspace_id=workspace.pk,
    )

    stats = notifications.aggregate(
        count=Count("pk"),
        unread_count=Count(
            "pk",
            filter=Q(read_at__isnull=True),
        ),
    )

    items = list(
        notifications
        .select_related(
            "workspace",
            "project",
            "task",
            "actor",
            "actor__profile",
        )
        .order_by("-created_at", "-pk")[:PREVIEW_LIMIT]
    )

    return {
        "count": stats["count"],
        "unread_count": stats["unread_count"],
        "items": items,
    }


def get_workspace_dashboard(*, workspace, user):
    """
    Build a personal dashboard for exactly one workspace.

    All project-based sections use the same access rules.
    Notification visibility uses the existing inbox policy.
    """

    now = timezone.now()
    today = timezone.localdate(now)

    due_soon_until = today + timedelta(days=UPCOMING_DAYS)
    upcoming_until = now + timedelta(days=UPCOMING_DAYS)

    accessible_project_ids = get_accessible_workspace_project_ids(
        workspace_slug=workspace.slug,
        user=user,
    )

    projects = Project.objects.filter(
        pk__in=accessible_project_ids,
    )

    visible_tasks = Task.objects.filter(
        project_id__in=accessible_project_ids,
    )

    active_tasks = visible_tasks.filter(
        status__in=ACTIVE_STATUSES,
    )

    my_tasks = active_tasks.filter(
        assignee_id=user.pk,
    )

    follow_up = (
        active_tasks
        .filter(created_by_id=user.pk)
        .exclude(assignee_id=user.pk)
    )

    overdue_tasks = my_tasks.filter(
        due_date__lt=today,
    )

    due_soon_tasks = my_tasks.filter(
        due_date__gte=today,
        due_date__lte=due_soon_until,
    )

    completed_tasks = visible_tasks.filter(
        assignee_id=user.pk,
        status=Task.Status.DONE,
    )

    # Calculate task counters in one aggregation query.
    stats = visible_tasks.aggregate(
        today_tasks=Count("pk", filter=Q(assignee_id=user.pk, status__in=ACTIVE_STATUSES, due_date=today)),
        my_tasks=Count(
            "pk",
            filter=Q(
                assignee_id=user.pk,
                status__in=ACTIVE_STATUSES,
            ),
        ),
        follow_up=Count(
            "pk",
            filter=(
                Q(
                    created_by_id=user.pk,
                    status__in=ACTIVE_STATUSES,
                )
                & ~Q(assignee_id=user.pk)
            ),
        ),
        overdue_tasks=Count(
            "pk",
            filter=Q(
                assignee_id=user.pk,
                status__in=ACTIVE_STATUSES,
                due_date__lt=today,
            ),
        ),
        due_soon_tasks=Count(
            "pk",
            filter=Q(
                assignee_id=user.pk,
                status__in=ACTIVE_STATUSES,
                due_date__gte=today,
                due_date__lte=due_soon_until,
            ),
        ),
        completed_tasks=Count(
            "pk",
            filter=Q(
                assignee_id=user.pk,
                status=Task.Status.DONE,
            ),
        ),
    )

    return {
        "today_tasks_count": stats["today_tasks"],
        "workspace_id": workspace.pk,
        "workspace_name": workspace.name,
        "as_of": today,
        "due_soon_until": due_soon_until,
        "upcoming_until": upcoming_until,

        "my_tasks": _task_section(
            my_tasks,
            stats["my_tasks"],
        ),

        "follow_up": _task_section(
            follow_up,
            stats["follow_up"],
        ),

        "overdue_tasks": _task_section(
            overdue_tasks,
            stats["overdue_tasks"],
        ),

        "due_soon_tasks": _task_section(
            due_soon_tasks,
            stats["due_soon_tasks"],
        ),

        "completed_tasks": _task_section(
            completed_tasks,
            stats["completed_tasks"],
            completed=True,
        ),

        "projects": _project_section(projects),

        "upcoming_reminders": _reminder_section(
            project_ids=accessible_project_ids,
            user=user,
            now=now,
            until=upcoming_until,
        ),

        "upcoming_events": _calendar_section(
            project_ids=accessible_project_ids,
            now=now,
            until=upcoming_until,
        ),

        "recent_notifications": _notification_section(
            workspace=workspace,
            user=user,
        ),
    }
