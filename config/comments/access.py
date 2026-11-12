from django.shortcuts import get_object_or_404

from tasks.access import get_task_or_404

from .models import Comment


def get_comment_task_or_404(
    *,
    workspace_slug,
    project_id,
    task_id,
    user,
):
    return get_task_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        task_id=task_id,
        user=user,
    )


def get_accessible_task_comments(
    *,
    workspace_slug,
    project_id,
    task_id,
    user,
):
    task = get_comment_task_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        task_id=task_id,
        user=user,
    )

    return Comment.objects.filter(
        task=task,
    ).select_related(
        "author",
        "author__profile", "attachment",
    ).prefetch_related("mentions")


def get_comment_or_404(
    *,
    workspace_slug,
    project_id,
    task_id,
    comment_id,
    user,
):
    task = get_comment_task_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        task_id=task_id,
        user=user,
    )

    return get_object_or_404(
        Comment.objects.select_related(
            "author",
            "author__profile", "attachment",
        ).prefetch_related("mentions"),
        pk=comment_id,
        task=task,
    )
