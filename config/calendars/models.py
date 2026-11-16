
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class CalendarEvent(models.Model):
    class EventType(models.TextChoices):
        EVENT = "event", "Event"
        MEETING = "meeting", "Meeting"
        DEADLINE = "deadline", "Deadline"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
        max_length=10000,
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.EVENT,
    )

    starts_at = models.DateTimeField()

    ends_at = models.DateTimeField()

    all_day = models.BooleanField(
        default=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_calendar_events",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["starts_at", "id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    event_type__in=[
                        "event",
                        "meeting",
                        "deadline",
                    ]
                ),
                name="calendar_valid_event_type",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="calendar_valid_time_range",
            ),
        ]

        indexes = [
            models.Index(
                fields=["project", "starts_at"],
                name="calendar_project_start_idx",
            ),
            models.Index(
                fields=["project", "ends_at"],
                name="calendar_project_end_idx",
            ),
        ]

    def __str__(self):
        return self.title
