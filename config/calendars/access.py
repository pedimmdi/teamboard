
from django.db.models import Q
from django.shortcuts import get_object_or_404

from calendars.models import CalendarEvent
from projects.access import (
    get_workspace_project_membership_or_404,
)
from projects.models import Project
from workspaces.access import get_membership_or_404
from workspaces.models import WorkspaceMembership


def get_calendar_project_access_or_404(
    *,
    workspace_slug,
    project_id,
    user,
    roles=None,
):
    """
    Reuse the existing project permission policy.
    Workspace owners/admins retain privileged access.
    """
    return get_workspace_project_membership_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
        roles=roles,
    )


def get_calendar_event_or_404(
    *,
    workspace_slug,
    project_id,
    event_id,
    user,
    roles=None,
):
    get_calendar_project_access_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
        roles=roles,
    )

    return get_object_or_404(
        CalendarEvent.objects.select_related(
            "project",
            "created_by",
        ),
        pk=event_id,
        project_id=project_id,
    )


def get_accessible_project_events(
    *,
    workspace_slug,
    project_id,
    user,
):
    get_calendar_project_access_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=user,
    )

    return CalendarEvent.objects.filter(
        project_id=project_id,
    ).select_related(
        "project",
        "created_by",
    )


def get_accessible_workspace_project_ids(
    *,
    workspace_slug,
    user,
):
    """
    Return project IDs the user can access in a workspace.

    Workspace owners/admins can access all projects.
    Regular members can access only joined projects.
    """
    membership = get_membership_or_404(
        workspace_slug,
        user,
    )

    queryset = Project.objects.filter(
        workspace=membership.workspace,
    )

    if membership.role not in (
        WorkspaceMembership.Role.OWNER,
        WorkspaceMembership.Role.ADMIN,
    ):
        queryset = queryset.filter(
            memberships__user=user,
        )

    return queryset.values_list("pk", flat=True)


def get_accessible_workspace_events(
    *,
    workspace_slug,
    user,
):
    """
    Permission-scoped queryset for aggregated calendars.
    """
    project_ids = get_accessible_workspace_project_ids(
        workspace_slug=workspace_slug,
        user=user,
    )

    return CalendarEvent.objects.filter(
        project_id__in=project_ids,
    ).select_related(
        "project",
        "created_by",
    )
