from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404

from comments.models import Comment
from projects.access import (
    get_workspace_project_membership_or_404,
)
from tasks.models import Task



def get_task_project_access_or_404(
    *,
    workspace_slug,
    project_id,
    user,
    roles=None,
):
    """
    Verify access to a project within a workspace.

    Workspace owners/admins have management access.
    Other users must have an active project membership.
    """

    return get_workspace_project_membership_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
        roles=roles,
    )


def get_task_or_404(
    *,
    workspace_slug,
    project_id,
    task_id,
    user,
    roles=None,
):
    """
    Return a task only after verifying project access.

    The task must belong to the requested project.
    """
    get_task_project_access_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
        roles=roles,
    )

    return get_object_or_404(
        Task.objects.select_related(
            "project",
            "assignee",
            "assignee__profile",
            "created_by",
            "created_by__profile",
        ),
        pk=task_id,
        project_id=project_id,
    )


def get_accessible_project_tasks(
    *,
    workspace_slug,
    project_id,
    user,
):
    """
    Return tasks from a project accessible to the user.

    The returned queryset is scoped to one project.
    """
    get_task_project_access_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
    )

    # Keep comment aggregation out of the paginator's total count. The page
    # query can use the comment FK index for each task it returns.
    comment_counts = (
        Comment.objects.filter(task_id=OuterRef("pk"))
        .order_by()
        .values("task_id")
        .annotate(total=Count("pk"))
        .values("total")
    )
    return (
        Task.objects.filter(project_id=project_id)
        .select_related("assignee__profile", "created_by__profile")
        .only(
            "project_id", "title", "description", "status", "priority", "due_date", "position",
            "created_at", "updated_at", "completed_at", "assignee__email", "assignee__profile__avatar",
            "created_by__email", "created_by__profile__avatar",
        )
        .annotate(comment_count=Coalesce(Subquery(comment_counts), 0))
    )
