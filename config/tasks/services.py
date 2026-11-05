from datetime import date, datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from projects.access import get_project_membership_or_404
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace


TASK_MANAGER_ROLES = {ProjectMembership.Role.MANAGER}


def _lock_project(*, project_id):
    """
    Lock the workspace first, then the project.

    This follows the locking order used by project services.
    """
    project_workspace_id = get_object_or_404(
        Project.objects.only("workspace_id"),
        pk=project_id,
    ).workspace_id

    workspace = get_object_or_404(
        Workspace.objects.select_for_update(),
        pk=project_workspace_id,
    )

    project = get_object_or_404(
        Project.objects.select_for_update(),
        pk=project_id,
        workspace=workspace,
    )

    return project


def _validate_assignee(*, project, assignee):
    """
    An assignee must be an active member of the project
    and its workspace.
    """
    if assignee is None:
        return

    is_project_member = ProjectMembership.objects.filter(
        project=project,
        user=assignee,
        project__workspace__memberships__user=assignee,
    ).exists()

    if not is_project_member:
        raise ValidationError({
            "assignee": (
                "Assignee must be a member of this project "
                "and its workspace."
            )
        })


def _compact_task_positions(*, project, status):
    """
    Reassign consecutive positions within a project/status column.

    Caller must hold the project lock inside a transaction.
    """
    tasks = list(
        Task.objects.filter(
            project=project,
            status=status,
        ).order_by("position", "pk")
    )

    changed_tasks = []

    for index, task in enumerate(tasks):
        if task.position != index:
            task.position = index
            changed_tasks.append(task)

    if changed_tasks:
        Task.objects.bulk_update(
            changed_tasks,
            ["position"],
        )


def _validate_due_date(value):
    """
    Accept a date or None.

    Reject datetime values because Task.due_date
    is a DateField, not a DateTimeField.
    """
    if value is None:
        return None

    if isinstance(value, datetime) or not isinstance(value, date):
        raise ValidationError({
            "due_date": "Due date must be a valid date."
        })

    return value


def _validate_task_fields(
    *,
    title,
    description,
    status,
    priority,
):
    if not isinstance(title, str):
        raise ValidationError({
            "title": "Title must be a string."
        })

    title = title.strip()

    if not title:
        raise ValidationError({
            "title": "Task title cannot be empty."
        })

    if len(title) > 200:
        raise ValidationError({
            "title": "Task title cannot exceed 200 characters."
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

    if status not in Task.Status.values:
        raise ValidationError({
            "status": "Invalid task status."
        })

    if priority not in Task.Priority.values:
        raise ValidationError({
            "priority": "Invalid task priority."
        })

    return title


@transaction.atomic
def create_task(
    *,
    project,
    actor,
    title,
    description="",
    status=Task.Status.TODO,
    priority=Task.Priority.MEDIUM,
    assignee=None,
    due_date=None,
):
    project = _lock_project(project_id=project.pk)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
    )

    title = _validate_task_fields(
        title=title,
        description=description,
        status=status,
        priority=priority,
    )

    _validate_assignee(
        project=project,
        assignee=assignee,
    )

    due_date = _validate_due_date(due_date)

    max_position = Task.objects.filter(
        project=project,
        status=status,
    ).aggregate(
        max_position=Max("position"),
    )["max_position"]

    next_position = (
        0 if max_position is None else max_position + 1
    )

    return Task.objects.create(
        project=project,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assignee=assignee,
        created_by=actor,
        due_date=due_date,
        position=next_position,
    )


@transaction.atomic
def update_task(
    *,
    task,
    actor,
    title=None,
    description=None,
    status=None,
    priority=None,
    due_date=None,
    update_due_date=False,
    assignee=None,
    update_assignee=False,
):
    project = _lock_project(project_id=task.project_id)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
    )

    task = get_object_or_404(
        Task.objects.select_for_update(),
        pk=task.pk,
        project=project,
    )

    new_title = task.title if title is None else title
    new_description = (
        task.description
        if description is None
        else description
    )
    new_status = task.status if status is None else status
    new_priority = (
        task.priority
        if priority is None
        else priority
    )

    new_title = _validate_task_fields(
        title=new_title,
        description=new_description,
        status=new_status,
        priority=new_priority,
    )

    if update_assignee:
        _validate_assignee(
            project=project,
            assignee=assignee,
        )
        task.assignee = assignee

    old_status = task.status
    status_changed = new_status != old_status

    if status_changed:
        max_position = Task.objects.filter(
            project=project,
            status=new_status,
        ).aggregate(
            max_position=Max("position"),
        )["max_position"]

        task.position = (
            0 if max_position is None else max_position + 1
        )

    task.title = new_title
    task.description = new_description
    task.status = new_status
    task.priority = new_priority

    if update_due_date:
        task.due_date = _validate_due_date(due_date)

    task.save()

    if status_changed:
        _compact_task_positions(
            project=project,
            status=old_status,
        )

    return task


@transaction.atomic
def delete_task(*, task, actor):
    project = _lock_project(project_id=task.project_id)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
        roles=TASK_MANAGER_ROLES,
    )

    task = get_object_or_404(
        Task.objects.select_for_update(),
        pk=task.pk,
        project=project,
    )

    old_status = task.status

    task.delete()

    _compact_task_positions(
        project=project,
        status=old_status,
    )


@transaction.atomic
def move_task(*, task, actor, status, position=None, before_task=None, placement=None):
    project = _lock_project(project_id=task.project_id)

    get_project_membership_or_404(
        project_id=project.pk,
        user=actor,
    )

    task = get_object_or_404(
        Task.objects.select_for_update(),
        pk=task.pk,
        project=project,
    )

    source_status = task.status

    if status not in Task.Status.values:
        raise ValidationError({
            "status": "Invalid task status."
        })

    if sum(value is not None for value in (position, before_task, placement)) != 1:
        raise ValidationError("Provide exactly one of position, before_task, or placement.")
    if position is not None:
        if isinstance(position, bool) or not isinstance(position, int):
            raise ValidationError({"position": "Position must be an integer."})
        if position < 0:
            raise ValidationError({"position": "Position must be non-negative."})
    if placement is not None and placement not in ("first", "last"):
        raise ValidationError({"placement": "Invalid placement."})

    # All task writes acquire this project's lock. Resolve the anchor here,
    # rather than trusting a position read by the browser before the move.
    anchor = None
    if before_task is not None:
        try:
            anchor_id = UUID(str(before_task))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError({"before_task": "Invalid destination task."})
        if anchor_id == task.pk:
            raise ValidationError({"before_task": "A task cannot be placed before itself."})
        anchor = get_object_or_404(Task, pk=anchor_id, project=project)
        if anchor.status != status:
            raise ValidationError({"before_task": "The destination task moved to another column. Refresh and try again."})

    source_tasks = list(
        Task.objects.filter(
            project=project,
            status=source_status,
        ).order_by("position", "pk")
    )

    if status == source_status:
        ordered_tasks = [
            item for item in source_tasks
            if item.pk != task.pk
        ]

        if anchor is not None:
            position = next(index for index, item in enumerate(ordered_tasks) if item.pk == anchor.pk)
        elif placement is not None:
            position = 0 if placement == "first" else len(ordered_tasks)

        if position > len(ordered_tasks):
            raise ValidationError({
                "position": "Position is out of range."
            })

        ordered_tasks.insert(position, task)

        changed_tasks = []

        for index, item in enumerate(ordered_tasks):
            if item.position != index:
                item.position = index
                changed_tasks.append(item)

        if changed_tasks:
            Task.objects.bulk_update(
                changed_tasks,
                ["position"],
            )

    else:
        destination_tasks = list(
            Task.objects.filter(
                project=project,
                status=status,
            ).order_by("position", "pk")
        )

        if anchor is not None:
            position = next(index for index, item in enumerate(destination_tasks) if item.pk == anchor.pk)
        elif placement is not None:
            position = 0 if placement == "first" else len(destination_tasks)

        if position > len(destination_tasks):
            raise ValidationError({
                "position": "Position is out of range."
            })

        remaining_source = [
            item for item in source_tasks
            if item.pk != task.pk
        ]

        task.status = status
        destination_tasks.insert(position, task)

        changed_source_tasks = []

        for index, item in enumerate(remaining_source):
            if item.position != index:
                item.position = index
                changed_source_tasks.append(item)

        changed_destination_tasks = []

        for index, item in enumerate(destination_tasks):
            if (
                item.position != index
                or item.pk == task.pk
            ):
                item.position = index
                changed_destination_tasks.append(item)

        if changed_source_tasks:
            Task.objects.bulk_update(
                changed_source_tasks,
                ["position"],
            )

        if changed_destination_tasks:
            Task.objects.bulk_update(
                changed_destination_tasks,
                ["status", "position"],
            )

    Task.objects.filter(
        pk=task.pk,
        project=project,
    ).update(
        updated_at=timezone.now(),
    )

    task.refresh_from_db()

    return task
