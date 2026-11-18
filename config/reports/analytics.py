from datetime import datetime, time, timedelta, timezone

from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import TruncDate, TruncWeek

from tasks.models import Task, TaskStatusHistory


def report_filters(filters, user, *, assignee_field="assignee_id"):
    conditions = {key: filters[key] for key in ("status", "priority") if key in filters}
    assignee = filters.get("assignee")
    if assignee is not None:
        conditions[assignee_field] = (
            None if assignee == "unassigned" else user.pk if assignee == "me" else int(assignee)
        )
    return conditions


def filter_current_tasks(tasks, filters, user):
    tasks = tasks.filter(**report_filters(filters, user))
    if "start_date" in filters:
        tasks = tasks.filter(
            created_at__gte=utc_start(filters["start_date"]),
            created_at__lt=utc_start(filters["end_date"] + timedelta(days=1)),
        )
    return tasks


def utc_start(day):
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def history_report(projects, filters, user, today):
    end = filters.get("end_date", today)
    start = filters.get("start_date")
    if start is None:
        start = end - timedelta(days=int(filters.get("period", "30d")[:-1]) - 1)
    days = (end - start).days + 1
    weekly = filters["granularity"] == "week"
    truncate = TruncWeek if weekly else TruncDate
    snapshots = TaskStatusHistory.objects.filter(project__in=projects)
    creation_snapshots = snapshots.filter(previous_status__isnull=True)
    conditions = report_filters(filters, user)
    legacy_tasks = Task.objects.filter(
        project__in=projects, **conditions,
    ).filter(~Exists(creation_snapshots.filter(task_id=OuterRef("pk"))))
    previous_start = start - timedelta(days=days)
    end_exclusive = end + timedelta(days=1)
    completions = snapshots.filter(status=Task.Status.DONE).filter(**conditions)

    def counts(queryset, field, first, end_before):
        rows = queryset.filter(**{
            field + "__gte": utc_start(first),
            field + "__lt": utc_start(end_before),
        }).order_by().annotate(bucket=truncate(field, tzinfo=timezone.utc)).values("bucket").annotate(
            count=Count("pk"),
        )
        return {
            (row["bucket"].date() if weekly else row["bucket"]): row["count"]
            for row in rows
        }

    def period(first, end_before):
        created = counts(creation_snapshots.filter(**conditions), "changed_at", first, end_before)
        for day, total in counts(legacy_tasks, "created_at", first, end_before).items():
            created[day] = created.get(day, 0) + total
        completed = counts(completions, "changed_at", first, end_before)
        day = first - timedelta(days=first.weekday()) if weekly else first
        while day < end_before:
            yield {
                "date": day,
                "start_date": max(day, first),
                "end_date": min(day + timedelta(days=6 if weekly else 0), end_before - timedelta(days=1)),
                "created": created.get(day, 0),
                "completed": completed.get(day, 0),
            }
            day += timedelta(days=7 if weekly else 1)

    coverage = MigrationRecorder.Migration.objects.filter(
        app="tasks", name="0006_track_task_status",
    ).values_list("applied", flat=True).first()
    return {
        "start_date": start, "end_date": end, "completion_tracking_since": coverage,
        "results": list(period(start, end_exclusive)),
        "previous_results": list(period(previous_start, start)),
    }


def workload_rows(tasks, today):
    active = ~Q(status=Task.Status.DONE)
    rows = tasks.order_by().values("assignee_id").annotate(
        total_tasks=Count("pk"),
        completed_tasks=Count("pk", filter=~active),
        overdue_tasks=Count("pk", filter=active & Q(due_date__lt=today)),
        due_soon_tasks=Count("pk", filter=active & Q(due_date__range=(today, today + timedelta(days=7)))),
    ).order_by("assignee_id")
    for row in rows:
        total, completed = row["total_tasks"], row["completed_tasks"]
        yield {
            **row, "assignee": row["assignee_id"], "active_tasks": total - completed,
            "completion_rate": round(completed * 100 / total, 2),
        }
