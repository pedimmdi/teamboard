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

    position = models.PositiveIntegerField(
        default=0,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(condition=Q(assignee__isnull=False), name="task_assignee_required"),
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
            models.Index(fields=["project", "created_at"], name="task_project_created_idx"),
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

class TaskStatusHistory(models.Model):
    """Snapshots survive task deletion.

    task_id deliberately has no Task foreign key. The BEFORE INSERT trigger
    records the initial snapshot before the task row exists.
    """
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE)
    task_id = models.UUIDField(db_index=True)
    previous_status = models.CharField(max_length=20, choices=Task.Status.choices, null=True)
    status = models.CharField(max_length=20, choices=Task.Status.choices)
    priority = models.CharField(max_length=10, choices=Task.Priority.choices)
    assignee_id = models.BigIntegerField(null=True)
    changed_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["project", "status", "changed_at"], name="task_history_report_idx"),
        ]
