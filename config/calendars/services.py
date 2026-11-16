
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from calendars.models import CalendarEvent
from projects.access import get_project_membership_or_404
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace


EVENT_MANAGER_ROLES = {ProjectMembership.Role.MANAGER}
UNSET = object()


def _lock_project(*, project_id):
    """
    Lock workspace first, then project.

    Follow the same lock ordering as task services.
    """
    workspace_id = get_object_or_404(
        Project.objects.only("workspace_id"),
        pk=project_id,
    ).workspace_id

    workspace = get_object_or_404(
        Workspace.objects.select_for_update(),
        pk=workspace_id,
    )

    return get_object_or_404(
        Project.objects.select_for_update(),
        pk=project_id,
        workspace=workspace,
    )


def _validate_event_fields(
    *,
    title,
    description,
    event_type,
    starts_at,
    ends_at,
    all_day,
):
    if not isinstance(title, str):
        raise ValidationError({
            "title": "Title must be a string."
        })

    title = title.strip()

    if not title:
        raise ValidationError({
            "title": "Event title cannot be empty."
        })

    if len(title) > 200:
        raise ValidationError({
            "title": "Title cannot exceed 200 characters."
        })

    if not isinstance(description, str):
        raise ValidationError({
            "description": "Description must be a string."
        })

    if len(description) > 10000:
        raise ValidationError({
            "description": (
                "Description cannot exceed 10000 characters."
            )
        })

    if event_type not in CalendarEvent.EventType.values:
        raise ValidationError({
            "event_type": "Invalid event type."
        })

    if not isinstance(all_day, bool):
        raise ValidationError({
            "all_day": "All day must be a boolean."
        })

    for field_name, value in (
        ("starts_at", starts_at),
        ("ends_at", ends_at),
    ):
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValidationError({
                field_name: (
                    "A timezone-aware datetime is required."
                )
            })

    if ends_at <= starts_at:
        raise ValidationError({
            "ends_at": (
                "End time must be after start time."
            )
        })

    if all_day:
        for field_name, value in (
            ("starts_at", starts_at),
            ("ends_at", ends_at),
        ):
            utc_value = value.astimezone(dt_timezone.utc)

            if (
                utc_value.hour != 0
                or utc_value.minute != 0
                or utc_value.second != 0
                or utc_value.microsecond != 0
            ):
                raise ValidationError({
                    field_name: (
                        "All-day events must use midnight UTC."
                    )
                })

    return title


@transaction.atomic
def create_calendar_event(
    *,
    project,
    actor,
    title,
    starts_at,
    ends_at,
    description="",
    event_type=CalendarEvent.EventType.EVENT,
    all_day=False,
):
    project = _lock_project(project_id=project.pk)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
    )

    title = _validate_event_fields(
        title=title,
        description=description,
        event_type=event_type,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
    )

    return CalendarEvent.objects.create(
        project=project,
        created_by=actor,
        title=title,
        description=description,
        event_type=event_type,
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
    )


@transaction.atomic
def update_calendar_event(
    *,
    event,
    actor,
    title=UNSET,
    description=UNSET,
    event_type=UNSET,
    starts_at=UNSET,
    ends_at=UNSET,
    all_day=UNSET,
):
    project = _lock_project(project_id=event.project_id)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
    )

    event = get_object_or_404(
        CalendarEvent.objects.select_for_update(),
        pk=event.pk,
        project=project,
    )

    values = {
        "title": event.title if title is UNSET else title,
        "description": (
            event.description
            if description is UNSET
            else description
        ),
        "event_type": (
            event.event_type
            if event_type is UNSET
            else event_type
        ),
        "starts_at": (
            event.starts_at
            if starts_at is UNSET
            else starts_at
        ),
        "ends_at": (
            event.ends_at
            if ends_at is UNSET
            else ends_at
        ),
        "all_day": (
            event.all_day
            if all_day is UNSET
            else all_day
        ),
    }

    values["title"] = _validate_event_fields(**values)

    changed_fields = []

    for field_name, value in values.items():
        if getattr(event, field_name) != value:
            setattr(event, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        event.save(
            update_fields=[*changed_fields, "updated_at"]
        )

    return event


@transaction.atomic
def delete_calendar_event(*, event, actor):
    project = _lock_project(project_id=event.project_id)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
        roles=EVENT_MANAGER_ROLES,
    )

    event = get_object_or_404(
        CalendarEvent.objects.select_for_update(),
        pk=event.pk,
        project=project,
    )

    event.delete()
