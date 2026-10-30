
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from projects.models import ProjectMembership
from workspaces.models import WorkspaceMembership


def get_project_membership_or_404(
    *,
    project_id,
    user,
    roles=None,
):
    membership = get_object_or_404(
        ProjectMembership.objects.select_related(
            "project",
            "project__workspace",
        ),
        project_id=project_id,
        user=user,
        project__workspace__memberships__user=user,
    )

    if roles is not None and membership.role not in roles:
        raise PermissionDenied(
            "You do not have permission to perform this action."
        )

    return membership


def get_workspace_project_membership_or_404(
    *,
    workspace_slug,
    project_id,
    user,
    roles=None,
):
    membership = get_object_or_404(
        ProjectMembership.objects.select_related(
            "project",
            "project__workspace",
        ),
        project_id=project_id,
        project__workspace__slug=workspace_slug,
        user=user,
        project__workspace__memberships__user=user,
    )

    if roles is not None and membership.role not in roles:
        raise PermissionDenied(
            "You do not have permission to perform this action."
        )

    return membership
