
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
