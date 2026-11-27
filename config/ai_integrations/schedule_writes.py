from datetime import datetime
from typing import Annotated
from uuid import UUID

from calendars.access import get_calendar_event_or_404
from calendars.api.v1.serializers import (
    CalendarEventCreateSerializer,
    CalendarEventUpdateSerializer,
)
from calendars.models import CalendarEvent
from calendars.services import create_calendar_event, update_calendar_event
from django.shortcuts import get_object_or_404
from projects.access import get_workspace_project_membership_or_404
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from rest_framework.exceptions import ValidationError
from tasks.access import get_task_or_404
from tasks.api.v1.reminders import ReminderWriteSerializer
from tasks.models import TaskReminder
from tasks.reminders import cancel_reminder, save_reminder

from .calendar_reads import OffsetDatetime
from .tool_schema import WorkspaceSlug

Title = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Description = Annotated[StrictStr, Field(max_length=10000)]
Timezone = Annotated[StrictStr, Field(min_length=1, max_length=64)]
DaysBefore = Annotated[StrictInt, Field(ge=0, le=365)]
LocalTime = Annotated[StrictStr, Field(pattern=r"^[0-9]{2}:[0-9]{2}(?::[0-9]{2})?$")]


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    event_type: CalendarEvent.EventType | None = None
    starts_at: OffsetDatetime | None = None
    ends_at: OffsetDatetime | None = None
    all_day: StrictBool | None = None


class EventWritten(BaseModel):
    event_id: UUID
    starts_at: datetime
    ends_at: datetime


class ReminderFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TaskReminder.Kind | None = None
    timezone: Timezone | None = None
    run_at: OffsetDatetime | None = None
    days_before: DaysBefore | None = None
    local_time: LocalTime | None = None


class ReminderWritten(BaseModel):
    reminder_id: UUID
    status: TaskReminder.Status
    run_at: datetime | None


def _event_result(event):
    return {"event_id": event.pk, "starts_at": event.starts_at, "ends_at": event.ends_at}


def _reminder_result(reminder):
    return {"reminder_id": reminder.pk, "status": reminder.status, "run_at": reminder.run_at}


def _reminder_data(data, reminder=None):
    serializer = ReminderWriteSerializer(data=data, partial=reminder is not None, context={"reminder": reminder})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def register_schedule_writes(server, annotations, write, validate):
    @server.tool(annotations=annotations)
    async def teamboard_create_calendar_event(
        workspace_slug: WorkspaceSlug, project_id: UUID, idempotency_key: UUID,
        title: Title, starts_at: OffsetDatetime, ends_at: OffsetDatetime,
        event_type: CalendarEvent.EventType = CalendarEvent.EventType.EVENT,
        description: Description = "", all_day: StrictBool = False,
    ) -> EventWritten:
        """Create an event with offset-aware times. All-day events use UTC midnight and an exclusive end."""
        data = dict(title=title, starts_at=starts_at.isoformat(), ends_at=ends_at.isoformat(),
                    description=description, event_type=event_type, all_day=all_day)

        def authorize(user):
            return get_workspace_project_membership_or_404(workspace_slug=workspace_slug, project_id=project_id, user=user).project

        def create(user, project):
            return _event_result(create_calendar_event(project=project, actor=user, **validate(CalendarEventCreateSerializer, data)))

        return EventWritten(**await write("create_calendar_event", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, **data}, authorize, create))

    @server.tool(annotations=annotations)
    async def teamboard_update_calendar_event(
        workspace_slug: WorkspaceSlug, project_id: UUID, event_id: UUID, idempotency_key: UUID, changes: EventPatch,
    ) -> EventWritten:
        """Change selected fields of an accessible calendar event."""
        data = changes.model_dump(mode="json", exclude_unset=True)

        def update(user, event):
            return _event_result(update_calendar_event(event=event, actor=user, **validate(CalendarEventUpdateSerializer, data)))

        return EventWritten(**await write("update_calendar_event", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "event": event_id, **data},
            lambda user: get_calendar_event_or_404(workspace_slug=workspace_slug, project_id=project_id, event_id=event_id, user=user), update))

    @server.tool(annotations=annotations)
    async def teamboard_create_task_reminder(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, idempotency_key: UUID, reminder: ReminderFields,
    ) -> ReminderWritten:
        """Create your private absolute or due-date-relative reminder. Supply an IANA timezone like Asia/Tehran."""
        data = reminder.model_dump(mode="json", exclude_unset=True)

        def create(user, task):
            return _reminder_result(save_reminder(task=task, actor=user, data=_reminder_data(data)))

        return ReminderWritten(**await write("create_task_reminder", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "task": task_id, **data},
            lambda user: get_task_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user), create))

    def get_reminder(user, workspace_slug, project_id, task_id, reminder_id):
        task = get_task_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user)
        return task, get_object_or_404(TaskReminder, task=task, recipient=user, pk=reminder_id)

    @server.tool(annotations=annotations)
    async def teamboard_update_task_reminder(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, reminder_id: UUID,
        idempotency_key: UUID, changes: ReminderFields,
    ) -> ReminderWritten:
        """Reschedule a private unsent reminder you own."""
        data = changes.model_dump(mode="json", exclude_unset=True)

        def update(user, target):
            task, reminder = target
            return _reminder_result(save_reminder(task=task, actor=user, reminder_id=reminder.pk,
                data=_reminder_data(data, reminder)))

        return ReminderWritten(**await write("update_task_reminder", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "task": task_id, "reminder": reminder_id, **data},
            lambda user: get_reminder(user, workspace_slug, project_id, task_id, reminder_id), update))

    @server.tool(annotations=annotations)
    async def teamboard_cancel_task_reminder(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, reminder_id: UUID, idempotency_key: UUID,
    ) -> ReminderWritten:
        """Cancel a private reminder you own. Delivery history remains available."""
        def cancel(user, target):
            task, reminder = target
            cancel_reminder(task=task, actor=user, reminder_id=reminder.pk)
            reminder.refresh_from_db(fields=["status"])
            if reminder.status != TaskReminder.Status.CANCELLED:
                raise ValidationError({"status": "The reminder has already been sent."})
            return _reminder_result(reminder)

        return ReminderWritten(**await write("cancel_task_reminder", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "task": task_id, "reminder": reminder_id},
            lambda user: get_reminder(user, workspace_slug, project_id, task_id, reminder_id), cancel))
