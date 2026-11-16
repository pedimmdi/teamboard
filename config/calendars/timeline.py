from django.utils import timezone
from datetime import datetime, time, timedelta, timezone as dt_timezone

from rest_framework.exceptions import ValidationError

from calendars.access import (
    get_accessible_project_events,
    get_accessible_workspace_events,
    get_accessible_workspace_project_ids,
)
from tasks.models import Task


MAX_TIMELINE_ITEMS_PER_TYPE = 500


def get_timeline_items(*, workspace_slug, user, start, end, project_id=None):
    if project_id is None:
        events = get_accessible_workspace_events(
            workspace_slug=workspace_slug,
            user=user,
        )
        project_ids = get_accessible_workspace_project_ids(
            workspace_slug=workspace_slug,
            user=user,
        )
        tasks = Task.objects.filter(
            project_id__in=project_ids,
        )
    else:
        events = get_accessible_project_events(
            workspace_slug=workspace_slug,
            project_id=project_id,
            user=user,
        )
        tasks = Task.objects.filter(
            project_id=project_id,
        )

    events = events.filter(
        starts_at__lt=end,
        ends_at__gt=start,
    ).order_by("starts_at", "id")

    # Task due_date is represented as midnight UTC.
    # Normalize incoming datetimes before calculating
    # the inclusive/exclusive date boundaries.
    start_utc = start.astimezone(dt_timezone.utc)
    end_utc = end.astimezone(dt_timezone.utc)

    first_day = start_utc.date()
    if start_utc.time() != time.min:
        first_day += timedelta(days=1)

    last_day_exclusive = end_utc.date()
    if end_utc.time() != time.min:
        last_day_exclusive += timedelta(days=1)

    tasks = tasks.filter(
        due_date__isnull=False,
        due_date__gte=first_day,
        due_date__lt=last_day_exclusive,
    ).select_related(
        "project",
        "assignee",
    ).order_by("due_date", "id")

    event_rows = list(
        events[:MAX_TIMELINE_ITEMS_PER_TYPE + 1]
    )
    task_rows = list(
        tasks[:MAX_TIMELINE_ITEMS_PER_TYPE + 1]
    )

    if (
        len(event_rows) > MAX_TIMELINE_ITEMS_PER_TYPE
        or len(task_rows) > MAX_TIMELINE_ITEMS_PER_TYPE
    ):
        raise ValidationError({
            "date_range": (
                "Too many timeline items. "
                "Choose a smaller date range."
            )
        })

    items = []

    for event in event_rows:
        items.append({
            "id": str(event.pk),
            "item_type": "event",
            "project": str(event.project_id),
            "title": event.title,
            "starts_at": event.starts_at,
            "ends_at": event.ends_at,
            "all_day": event.all_day,
            "event_type": event.event_type,
            "task_status": None,
            "task_priority": None,
        })

    for task in task_rows:
        due_at = datetime.combine(
            task.due_date,
            time.min,
            tzinfo=dt_timezone.utc,
        )

        items.append({
            "id": str(task.pk),
            "item_type": "task",
            "project": str(task.project_id),
            "title": task.title,
            "starts_at": due_at,
            "ends_at": due_at + timedelta(days=1),
            "all_day": True,
            "event_type": None,
            "task_status": task.status,
            "task_priority": task.priority,
        })

    items.sort(
        key=lambda item: (
            item["starts_at"],
            item["item_type"],
            item["id"],
        )
    )

    return items
