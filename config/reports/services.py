from django.db.models import Count, Q
from django.utils import timezone

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import WorkspaceMembership


def _task_overview(tasks, today):
    completed = Q(status=Task.Status.DONE)
    counts = tasks.aggregate(
        total_tasks=Count("pk"),
        completed_tasks=Count("pk", filter=completed),
        overdue_tasks=Count("pk", filter=Q(due_date__lt=today) & ~completed),
        unassigned_tasks=Count("pk", filter=Q(assignee__isnull=True)),
        **{f"status_{value}": Count("pk", filter=Q(status=value)) for value in Task.Status.values},
        **{f"priority_{value}": Count("pk", filter=Q(priority=value)) for value in Task.Priority.values},
    )
    status_distribution = {value: counts.pop(f"status_{value}") for value in Task.Status.values}
    priority_distribution = {value: counts.pop(f"priority_{value}") for value in Task.Priority.values}
    total, done = counts["total_tasks"], counts["completed_tasks"]
    summary = {
        **counts,
        "active_tasks": total - done,
        "completion_rate": round(done * 100 / total, 2) if total else 0.0,
    }
    return summary, status_distribution, priority_distribution


def get_project_report(*, project, today=None):
    """
    Calculate current project analytics.

    All calculations are performed using database
    aggregation rather than loading tasks into Python.
    """
    if today is None:
        today = timezone.localdate()

    tasks = Task.objects.filter(project=project)

    summary, status_counts, priority_counts = _task_overview(tasks, today)

    workload_counts = {
        row["assignee_id"]: row
        for row in tasks.filter(
            assignee__isnull=False
        ).values("assignee_id").annotate(
            total_tasks=Count("pk"),
            completed_tasks=Count(
                "pk",
                filter=Q(status=Task.Status.DONE),
            ),
            overdue_tasks=Count(
                "pk",
                filter=(
                    Q(due_date__lt=today)
                    & ~Q(status=Task.Status.DONE)
                ),
            ),
        )
    }

    memberships = (
        ProjectMembership.objects
        .filter(project=project)
        .order_by("joined_at", "pk")
        .values("user_id", "user__email", "role")
    )

    workload = []

    for membership in memberships:
        counts = workload_counts.get(
            membership["user_id"], {}
        )

        workload.append({
            "user_id": membership["user_id"],
            "user_email": membership["user__email"],
            "role": membership["role"],
            "total_tasks": counts.get(
                "total_tasks", 0
            ),
            "completed_tasks": counts.get(
                "completed_tasks", 0
            ),
            "overdue_tasks": counts.get(
                "overdue_tasks", 0
            ),
        })

    return {
        "project_id": project.pk,
        "project_name": project.name,
        "as_of": today,
        "summary": summary,
        "status_distribution": status_counts,
        "priority_distribution": priority_counts,
        "member_workload": workload,
    }


def get_workspace_report(*, workspace, user, today=None):
    """
    Aggregate analytics across projects visible to the user.
    """
    if today is None:
        today = timezone.localdate()

    membership = WorkspaceMembership.objects.get(
        workspace=workspace,
        user=user,
    )

    projects = Project.objects.filter(
        workspace=workspace,
    )

    if membership.role not in (
        WorkspaceMembership.Role.OWNER,
        WorkspaceMembership.Role.ADMIN,
    ):
        projects = projects.filter(
            memberships__user=user,
        )

    project_ids = projects.values("pk")

    tasks = Task.objects.filter(
        project_id__in=project_ids,
    )

    summary, status_distribution, priority_distribution = _task_overview(tasks, today)

    project_rows = list(
        projects.annotate(
            total_tasks=Count("tasks"),
            completed_tasks=Count(
                "tasks",
                filter=Q(tasks__status=Task.Status.DONE),
            ),
            overdue_tasks=Count(
                "tasks",
                filter=(
                    Q(tasks__due_date__lt=today)
                    & ~Q(tasks__status=Task.Status.DONE)
                ),
            ),
        )
        .order_by("name", "pk")
        .values(
            "id",
            "name",
            "total_tasks",
            "completed_tasks",
            "overdue_tasks",
        )
    )

    project_summaries = []

    for row in project_rows:
        project_total = row["total_tasks"]
        project_completed = row["completed_tasks"]

        project_summaries.append({
            "project_id": row["id"],
            "project_name": row["name"],
            "total_tasks": project_total,
            "completed_tasks": project_completed,
            "overdue_tasks": row["overdue_tasks"],
            "completion_rate": (
                round(
                    project_completed * 100 / project_total,
                    2,
                )
                if project_total else 0.0
            ),
        })

    return {
        "workspace_id": workspace.pk,
        "workspace_name": workspace.name,
        "as_of": today,
        "total_projects": len(project_summaries),
        "summary": summary,
        "status_distribution": status_distribution,
        "priority_distribution": priority_distribution,
        "projects": project_summaries,
    }
