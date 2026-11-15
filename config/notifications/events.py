
from uuid import uuid4

from notifications.models import Notification
from notifications.services import create_notification


def notify_task_assigned(*, task, actor):
    """
    Create a notification for a task assignment.

    The caller must invoke this inside the same
    database transaction as the task assignment.
    """

    if task.assignee_id is None:
        return None, False

    return create_notification(
        recipient=task.assignee,
        actor=actor,
        event_type=Notification.EventType.TASK_ASSIGNED,
        workspace=task.project.workspace,
        project=task.project,
        task=task,
        deduplication_key=(
            f"task_assigned:{task.pk}:{uuid4()}"
        ),
        payload={},
    )

def notify_task_updated(*, task, actor, changed_fields):
    """
    Notify the current assignee about meaningful task changes.

    The caller must invoke this inside the same
    database transaction as the task update.
    """

    allowed_fields = {
        "title",
        "description",
        "status",
        "priority",
        "due_date",
    }

    fields = sorted(set(changed_fields) & allowed_fields)

    if not fields or task.assignee_id is None:
        return None, False

    return create_notification(
        recipient=task.assignee,
        actor=actor,
        event_type=Notification.EventType.TASK_UPDATED,
        workspace=task.project.workspace,
        project=task.project,
        task=task,
        deduplication_key=f"task_updated:{task.pk}:{uuid4()}",
        payload={"changed_fields": fields},
    )

def notify_comment_mentioned(*, comment, actor, recipient):
    """
    Notify one user mentioned in a comment.

    Must be called inside the comment transaction.
    """

    return create_notification(
        recipient=recipient,
        actor=actor,
        event_type=Notification.EventType.COMMENT_MENTIONED,
        workspace=comment.task.project.workspace,
        project=comment.task.project,
        task=comment.task,
        deduplication_key=(
            f"comment_mentioned:{comment.pk}:{recipient.pk}"
        ),
        payload={"comment_id": str(comment.pk)},
    )


def notify_comment_replied(*, comment, actor):
    """
    Notify the parent comment's author about a reply.

    Must be called inside the comment transaction.
    """

    if comment.reply_to_id is None:
        return None, False

    parent = comment.reply_to

    if parent is None or parent.author_id is None:
        return None, False

    return create_notification(
        recipient=parent.author,
        actor=actor,
        event_type=Notification.EventType.COMMENT_REPLIED,
        workspace=comment.task.project.workspace,
        project=comment.task.project,
        task=comment.task,
        deduplication_key=(
            f"comment_replied:{comment.pk}:{parent.author_id}"
        ),
        payload={
            "comment_id": str(comment.pk),
            "parent_comment_id": str(parent.pk),
        },
    )

def notify_project_member_added(*, membership, actor):
    """
    Notify a user who has been added to a project.

    Must be called inside the membership transaction.
    """

    return create_notification(
        recipient=membership.user,
        actor=actor,
        event_type=Notification.EventType.PROJECT_MEMBER_ADDED,
        workspace=membership.project.workspace,
        project=membership.project,
        deduplication_key=(
            f"project_member_added:{membership.pk}"
        ),
        payload={
            "role": membership.role,
        },
    )


def notify_project_role_changed(
    *,
    membership,
    actor,
    old_role,
):
    """
    Notify a project member about a real role change.

    Must be called inside the role-change transaction.
    """

    if old_role == membership.role:
        return None, False

    return create_notification(
        recipient=membership.user,
        actor=actor,
        event_type=Notification.EventType.PROJECT_ROLE_CHANGED,
        workspace=membership.project.workspace,
        project=membership.project,
        deduplication_key=(
            f"project_role_changed:{membership.pk}:{uuid4()}"
        ),
        payload={
            "old_role": old_role,
            "new_role": membership.role,
        },
    )


def notify_workspace_invited(*, invitation, recipient):
    """
    Notify an existing user about a workspace invitation.

    Invitation tokens must never be stored in the payload.
    """

    return create_notification(
        recipient=recipient,
        actor=invitation.invited_by,
        event_type=Notification.EventType.WORKSPACE_INVITED,
        workspace=invitation.workspace,
        deduplication_key=(
            f"workspace_invited:{invitation.pk}:{recipient.pk}"
        ),
        payload={
            "invitation_id": str(invitation.pk),
        },
    )


def notify_workspace_role_changed(
    *,
    membership,
    actor,
    old_role,
):
    """
    Notify a workspace member about a real role change.

    Must be called inside the membership transaction.
    """

    if old_role == membership.role:
        return None, False

    return create_notification(
        recipient=membership.user,
        actor=actor,
        event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        workspace=membership.workspace,
        deduplication_key=(
            f"workspace_role_changed:{membership.pk}:{uuid4()}"
        ),
        payload={
            "old_role": old_role,
            "new_role": membership.role,
        },
    )
