
from rest_framework.exceptions import ValidationError

from notifications.models import Notification


WORKSPACE_EVENTS = frozenset({
    Notification.EventType.WORKSPACE_INVITED,
    Notification.EventType.WORKSPACE_ROLE_CHANGED,
})

PROJECT_EVENTS = frozenset({
    Notification.EventType.PROJECT_MEMBER_ADDED,
    Notification.EventType.PROJECT_ROLE_CHANGED,
})

TASK_EVENTS = frozenset({
    Notification.EventType.TASK_ASSIGNED,
    Notification.EventType.TASK_UPDATED,
    Notification.EventType.TASK_REMINDER,
    Notification.EventType.COMMENT_MENTIONED,
    Notification.EventType.COMMENT_REPLIED,
})


def validate_notification_scope(
    *,
    event_type,
    workspace,
    project,
    task,
):
    """
    Validate required and forbidden scope fields
    for each notification event type.
    """

    if event_type not in Notification.EventType.values:
        raise ValidationError({
            "event_type": "Invalid notification event type.",
        })

    if workspace is None:
        raise ValidationError({
            "workspace": "Workspace is required.",
        })

    if event_type in WORKSPACE_EVENTS:
        if project is not None:
            raise ValidationError({
                "project": (
                    "Project is not allowed for workspace events."
                ),
            })

        if task is not None:
            raise ValidationError({
                "task": (
                    "Task is not allowed for workspace events."
                ),
            })

        return

    if event_type in PROJECT_EVENTS:
        if project is None:
            raise ValidationError({
                "project": "Project is required.",
            })

        if task is not None:
            raise ValidationError({
                "task": (
                    "Task is not allowed for project events."
                ),
            })

        return

    if event_type in TASK_EVENTS:
        if project is None:
            raise ValidationError({
                "project": "Project is required.",
            })

        if task is None:
            raise ValidationError({
                "task": "Task is required.",
            })

        return

    raise ValidationError({
        "event_type": "Unsupported notification event type.",
    })
