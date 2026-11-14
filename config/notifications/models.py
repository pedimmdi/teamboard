
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    class EventType(models.TextChoices):
        TASK_ASSIGNED = "task_assigned", "Task Assigned"
        TASK_UPDATED = "task_updated", "Task Updated"
        COMMENT_MENTIONED = "comment_mentioned", "Comment Mentioned"
        COMMENT_REPLIED = "comment_replied", "Comment Replied"
        WORKSPACE_INVITED = "workspace_invited", "Workspace Invited"
        WORKSPACE_ROLE_CHANGED = (
            "workspace_role_changed",
            "Workspace Role Changed",
        )
        PROJECT_MEMBER_ADDED = (
            "project_member_added",
            "Project Member Added",
        )
        PROJECT_ROLE_CHANGED = (
            "project_role_changed",
            "Project Role Changed",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )

    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
    )

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    payload = models.JSONField(
        default=dict,
        blank=True,
    )

    deduplication_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(
                fields=["recipient", "-created_at", "-id"],
                name="notif_recipient_date_idx",
            ),
            models.Index(
                fields=["recipient", "-created_at"],
                condition=Q(read_at__isnull=True),
                name="notif_unread_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(event_type__in=[
                    "task_assigned",
                    "task_updated",
                    "comment_mentioned",
                    "comment_replied",
                    "workspace_invited",
                    "workspace_role_changed",
                    "project_member_added",
                    "project_role_changed",
                ]),
                name="valid_notification_event_type",
            ),
        ]

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return (
            f"{self.event_type} for "
            f"{self.recipient_id}"
        )
