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


class TaskReminder(models.Model):
    class Kind(models.TextChoices):
        ABSOLUTE = "absolute", "Absolute"
        RELATIVE = "relative", "Relative to due date"
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISABLED = "disabled", "No due date"
        INVALID = "invalid", "Needs rescheduling"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed; retry scheduled"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="reminders")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_reminders")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    timezone = models.CharField(max_length=64, default="UTC")
    run_at = models.DateTimeField(null=True, blank=True)
    days_before = models.PositiveSmallIntegerField(null=True, blank=True)
    local_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    notification = models.OneToOneField("notifications.Notification", on_delete=models.SET_NULL, null=True, blank=True, related_name="reminder")
    needs_recalculation = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["run_at", "id"], condition=Q(status="pending"), name="reminder_due_idx"),
            models.Index(fields=["retry_at", "id"], condition=Q(status="failed"), name="reminder_retry_idx"),
            models.Index(fields=["task", "recipient"], name="reminder_owner_idx"),
            models.Index(fields=["id"], condition=Q(needs_recalculation=True), name="reminder_recalc_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(kind="absolute", run_at__isnull=False, days_before__isnull=True, local_time__isnull=True) | Q(kind="relative", days_before__isnull=False, local_time__isnull=False, days_before__lte=365), name="reminder_valid_kind"),
            models.CheckConstraint(condition=Q(status__in=["pending", "disabled", "invalid", "sent", "cancelled", "failed"]), name="reminder_valid_status"),
            models.CheckConstraint(condition=~Q(status="sent") | Q(sent_at__isnull=False), name="reminder_sent_timestamp"),
            models.UniqueConstraint(fields=["task", "recipient", "run_at"], condition=Q(status="pending"), name="reminder_unique_active_time"),
        ]
