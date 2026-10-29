from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from workspaces.models import Workspace, WorkspaceMembership


def get_membership_or_404(
    slug,
    user,
    roles=None,
    *,
    for_update=False,
    permission_message=None,
):
    if for_update:
        workspace_id = (
            Workspace.objects
            .filter(
                slug=slug,
                memberships__user=user,
            )
            .values_list("pk", flat=True)
            .first()
        )

        if workspace_id is None:
            raise Http404

        # Lock the workspace without the membership join/distinct.
        workspace = get_object_or_404(
            Workspace.objects.select_for_update(),
            pk=workspace_id,
        )

        # Lock the current user's membership separately.
        membership = get_object_or_404(
            WorkspaceMembership.objects.select_for_update(),
            workspace=workspace,
            user=user,
        )
    else:
        membership = get_object_or_404(
            WorkspaceMembership.objects.select_related("workspace"),
            workspace__slug=slug,
            user=user,
        )
        workspace = membership.workspace

    if roles is not None and membership.role not in roles:
        raise PermissionDenied(
            permission_message
            or "You do not have permission to perform this action."
        )

    return membership
