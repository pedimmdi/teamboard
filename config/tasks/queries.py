from comments.models import Comment
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from tasks.models import Task


def with_comment_count(queryset):
    # A correlated count keeps comment aggregation out of the paginator count.
    comment_counts = (
        Comment.objects.filter(task_id=OuterRef("pk"))
        .order_by()
        .values("task_id")
        .annotate(total=Count("pk"))
        .values("total")
    )
    return queryset.annotate(comment_count=Coalesce(Subquery(comment_counts), 0))


def filter_tasks(
    queryset,
    *,
    statuses=None,
    priority=None,
    assignee_id=None,
    due_on=None,
    due_before=None,
    overdue_before=None,
    search=None,
):
    filters = {
        key: value
        for key, value in {
            "status__in": statuses,
            "priority": priority,
            "assignee_id": assignee_id,
            "due_date": due_on,
            "due_date__lt": due_before,
        }.items()
        if value is not None
    }
    queryset = queryset.filter(**filters)
    if overdue_before is not None:
        queryset = queryset.filter(due_date__lt=overdue_before).exclude(
            status=Task.Status.DONE
        )
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    return queryset
