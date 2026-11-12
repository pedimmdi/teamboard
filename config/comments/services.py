
import re
from uuid import uuid4

from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from projects.access import get_project_membership_or_404
from projects.models import ProjectMembership
from tasks.models import Task

from .models import Comment, CommentAttachment
from .storage import attachment_storage, validate_attachment


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


MENTION = re.compile(r"(?<![\w@])@([\w.+-]+@[\w-]+(?:\.[\w-]+)+)")


def sync_mentions(comment):
    emails = {email.lower() for email in MENTION.findall(comment.body)}
    users = ProjectMembership.objects.filter(
        project_id=comment.task.project_id, user__is_active=True,
    ).annotate(email=Lower("user__email")).filter(email__in=emails).values_list("user_id", flat=True)
    comment.mentions.set(users)


@transaction.atomic
def create_comment(*, task, actor, body, reply_to=None, attachment=None):
    task = get_object_or_404(
        Task,
        pk=task.pk,
        project_id=task.project_id,
    )

    ensure_comment_access(
        project_id=task.project_id,
        actor=actor,
    )

    parent = None
    if reply_to is not None:
        parent = Comment.objects.select_for_update().filter(pk=reply_to, task=task).first()
        if parent is None:
            raise ValidationError({"reply_to": "Choose a comment on this task."})

    if attachment is not None:
        validate_attachment(attachment)
    body = validate_comment_body(body) if body or attachment is None else ""
    comment = Comment.objects.create(task=task, author=actor, body=body, reply_to=parent)
    sync_mentions(comment)
    if attachment is not None:
        storage = attachment_storage()
        key = storage.save(f"uploads/{uuid4().hex}", attachment)
        try:
            CommentAttachment.objects.create(
                comment=comment, filename=attachment.name, size=attachment.size, storage_key=key,
            )
        except Exception:
            storage.delete(key)
            raise
    return comment


@transaction.atomic
def update_comment(*, comment, actor, body):
    comment = get_object_or_404(
        Comment.objects.select_for_update(of=("self",)).select_related("task"),
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

    comment.body = "" if isinstance(body, str) and not body.strip() and hasattr(comment, "attachment") else validate_comment_body(body)
    comment.edited_at = timezone.now()
    comment.save(update_fields=["body", "updated_at", "edited_at"])
    sync_mentions(comment)

    return comment


@transaction.atomic
def delete_comment(*, comment, actor):
    comment = get_object_or_404(
        Comment.objects.select_for_update(of=("self",)).select_related("task"),
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
