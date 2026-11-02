import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        IN_REVIEW = "in_review", "In Review"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(
        blank=True,
        max_length=10000,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "todo",
                        "in_progress",
                        "in_review",
                        "done",
                    ]
                ),
                name="valid_task_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    priority__in=[
                        "low",
                        "medium",
                        "high",
                        "urgent",
                    ]
                ),
                name="valid_task_priority",
            ),
        ]

        indexes = [
            models.Index(
                fields=["project", "status"],
                name="task_project_status_idx",
            ),
            models.Index(
                fields=["project", "priority"],
                name="task_project_priority_idx",
            ),
            models.Index(
                fields=["assignee", "status"],
                name="task_assignee_status_idx",
            ),
            models.Index(
                fields=["project", "due_date"],
                name="task_project_due_idx",
            ),
        ]

    def __str__(self):
        return self.title
