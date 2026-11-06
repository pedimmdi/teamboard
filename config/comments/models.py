
import uuid

from django.conf import settings
from django.db import models


class Comment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_comments",
    )

    body = models.TextField(
        max_length=5000,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["created_at", "id"]

        indexes = [
            models.Index(
                fields=["task", "created_at", "id"],
                name="comment_task_date_idx",
            ),
        ]

    def __str__(self):
        return f"Comment {self.pk} on task {self.task_id}"
