from datetime import date, datetime

from django.db import transaction
from django.shortcuts import get_object_or_404
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

    return Task.objects.create(
        project=project,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assignee=assignee,
        created_by=actor,
        due_date=due_date,
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

    task.title = new_title
    task.description = new_description
    task.status = new_status
    task.priority = new_priority

    if update_due_date:
        task.due_date = _validate_due_date(due_date)

    task.save()

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

    task.delete()
