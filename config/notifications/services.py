
import json

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Notification


MAX_PAYLOAD_BYTES = 4096


def validate_notification_data(
    *,
    recipient,
    actor,
    event_type,
    workspace,
    project,
    task,
    payload,
    deduplication_key,
):
    if recipient is None or recipient.pk is None:
        raise ValidationError({
            "recipient": "A saved recipient is required.",
        })

    if not recipient.is_active:
        raise ValidationError({
            "recipient": "Recipient must be active.",
        })

    if actor is not None and actor.pk is None:
        raise ValidationError({
            "actor": "Actor must be saved.",
        })

    if event_type not in Notification.EventType.values:
        raise ValidationError({
            "event_type": "Invalid notification event type.",
        })

    if not isinstance(deduplication_key, str):
        raise ValidationError({
            "deduplication_key": "A unique event key is required.",
        })

    if (
        not deduplication_key
        or deduplication_key != deduplication_key.strip()
        or len(deduplication_key) > 255
    ):
        raise ValidationError({
            "deduplication_key": "Invalid event key.",
        })

    if not isinstance(payload, dict):
        raise ValidationError({
            "payload": "Payload must be an object.",
        })

    try:
        encoded_payload = json.dumps(
            payload,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ValidationError({
            "payload": "Payload must contain valid JSON values.",
        })

    if len(encoded_payload) > MAX_PAYLOAD_BYTES:
        raise ValidationError({
            "payload": "Payload is too large.",
        })

    for field_name, obj in (
        ("workspace", workspace),
        ("project", project),
        ("task", task),
    ):
        if obj is not None and obj.pk is None:
            raise ValidationError({
                field_name: "Related object must be saved.",
            })

    if project is not None:
        if workspace is None:
            raise ValidationError({
                "workspace": "Workspace is required for a project.",
            })

        if project.workspace_id != workspace.pk:
            raise ValidationError({
                "project": "Project does not belong to workspace.",
            })

    if task is not None:
        if project is None:
            raise ValidationError({
                "project": "Project is required for a task.",
            })

        if task.project_id != project.pk:
            raise ValidationError({
                "task": "Task does not belong to project.",
            })


@transaction.atomic
def create_notification(
    *,
    recipient,
    event_type,
    deduplication_key,
    actor=None,
    workspace=None,
    project=None,
    task=None,
    payload=None,
):
    """
    Create one persistent in-app notification.

    Returns:
        (notification, created)

    A self-notification is skipped and returns (None, False).

    The deduplication key must uniquely identify one
    notification delivery, including its recipient.
    """

    if payload is None:
        payload = {}

    validate_notification_data(
        recipient=recipient,
        actor=actor,
        event_type=event_type,
        workspace=workspace,
        project=project,
        task=task,
        payload=payload,
        deduplication_key=deduplication_key,
    )

    if actor is not None and actor.pk == recipient.pk:
        return None, False

    defaults = {
        "recipient": recipient,
        "actor": actor,
        "event_type": event_type,
        "workspace": workspace,
        "project": project,
        "task": task,
        "payload": payload,
    }

    notification, created = Notification.objects.get_or_create(
        deduplication_key=deduplication_key,
        defaults=defaults,
    )

    if not created:
        same_event = (
            notification.recipient_id == recipient.pk
            and notification.actor_id == (
                actor.pk if actor is not None else None
            )
            and notification.event_type == event_type
            and notification.workspace_id == (
                workspace.pk if workspace is not None else None
            )
            and notification.project_id == (
                project.pk if project is not None else None
            )
            and notification.task_id == (
                task.pk if task is not None else None
            )
            and notification.payload == payload
        )

        if not same_event:
            raise ValidationError({
                "deduplication_key": (
                    "This key belongs to a different notification."
                ),
            })

    return notification, created
