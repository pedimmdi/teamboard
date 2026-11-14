
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
