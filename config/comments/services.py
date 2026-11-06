
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from projects.access import get_project_membership_or_404
from projects.models import ProjectMembership
from tasks.models import Task

from .models import Comment


MAX_COMMENT_LENGTH = 5000


def validate_comment_body(body):
    if not isinstance(body, str):
        raise ValidationError({
            "body": "Comment body must be a string.",
        })

    body = body.strip()

    if not body:
        raise ValidationError({
            "body": "Comment cannot be empty.",
        })

    if len(body) > MAX_COMMENT_LENGTH:
        raise ValidationError({
            "body": "Comment cannot exceed 5000 characters.",
        })

    return body


def ensure_comment_access(*, project_id, actor):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication required.")

    return get_project_membership_or_404(
        project_id=project_id,
        user=actor,
    )


def can_delete_comment(*, comment, actor):
    if comment.author_id == actor.pk:
        return True

    try:
        get_project_membership_or_404(
            project_id=comment.task.project_id,
            user=actor,
            roles={ProjectMembership.Role.MANAGER},
        )
    except (PermissionDenied, Http404):
        return False

    return True


@transaction.atomic
def create_comment(*, task, actor, body):
    task = get_object_or_404(
        Task,
        pk=task.pk,
        project_id=task.project_id,
    )

    ensure_comment_access(
        project_id=task.project_id,
        actor=actor,
    )

    body = validate_comment_body(body)

    return Comment.objects.create(
        task=task,
        author=actor,
        body=body,
    )


@transaction.atomic
def update_comment(*, comment, actor, body):
    comment = get_object_or_404(
        Comment.objects.select_for_update().select_related("task"),
        pk=comment.pk,
        task_id=comment.task_id,
    )

    ensure_comment_access(
        project_id=comment.task.project_id,
        actor=actor,
    )

    if comment.author_id != actor.pk:
        raise PermissionDenied(
            "Only the author can edit this comment."
        )

    comment.body = validate_comment_body(body)
    comment.save(update_fields=["body", "updated_at"])

    return comment


@transaction.atomic
def delete_comment(*, comment, actor):
    comment = get_object_or_404(
        Comment.objects.select_for_update().select_related("task"),
        pk=comment.pk,
        task_id=comment.task_id,
    )

    ensure_comment_access(
        project_id=comment.task.project_id,
        actor=actor,
    )

    if not can_delete_comment(comment=comment, actor=actor):
        raise PermissionDenied(
            "You do not have permission to delete this comment."
        )

    comment.delete()
