from django.db.models import Count
from django.shortcuts import get_object_or_404

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

    return Task.objects.filter(
        project_id=project_id,
    ).select_related(
        "assignee",
        "assignee__profile",
        "created_by",
        "created_by__profile",
    ).annotate(comment_count=Count("comments"))
