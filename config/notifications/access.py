
from django.db.models import (
    CharField,
    Exists,
    F,
    OuterRef,
    Q,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils import timezone

from notifications.models import Notification
from notifications.scopes import PROJECT_EVENTS, TASK_EVENTS
from projects.models import ProjectMembership
from workspaces.models import (
    WorkspaceInvitation,
    WorkspaceMembership,
)


def get_accessible_notifications(user):
    """
    Return notifications visible to the authenticated user.

    Invitation notifications require a matching, active
    invitation addressed to the recipient's current email.

    Other workspace notifications require workspace membership.

    Project/task notifications require workspace membership
    and project membership or workspace management access.

    Notifications with missing or inconsistent scopes are hidden.
    """

    if not user.is_authenticated or not user.is_active:
        return Notification.objects.none()

    workspace_membership = WorkspaceMembership.objects.filter(
        workspace_id=OuterRef("workspace_id"),
        user=user,
    )

    workspace_management = workspace_membership.filter(
        role__in=[
            WorkspaceMembership.Role.OWNER,
            WorkspaceMembership.Role.ADMIN,
        ],
    )

    project_membership = ProjectMembership.objects.filter(
        project_id=OuterRef("project_id"),
        user=user,
    )

    active_invitation = (
        WorkspaceInvitation.objects
        .annotate(
            invitation_id_text=Cast(
                "id",
                output_field=CharField(),
            ),
        )
        .filter(
            invitation_id_text=OuterRef(
                "invitation_id_text"
            ),
            workspace_id=OuterRef("workspace_id"),
            email__iexact=user.email,
            status=WorkspaceInvitation.Status.PENDING,
            expires_at__gt=timezone.now(),
        )
    )

    invitation_access = (
        Q(
            event_type=Notification.EventType.WORKSPACE_INVITED,
            workspace__isnull=False,
            project__isnull=True,
            task__isnull=True,
        )
        & Q(has_active_invitation=True)
    )

    workspace_access = (
        Q(
            event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
            workspace__isnull=False,
            project__isnull=True,
            task__isnull=True,
        )
        & Q(has_workspace_access=True)
    )

    project_access = (
        Q(
            event_type__in=PROJECT_EVENTS,
            workspace__isnull=False,
            project__isnull=False,
            task__isnull=True,
        )
        & Q(has_workspace_access=True)
        & (
            Q(has_workspace_management=True)
            | Q(has_project_access=True)
        )
    )

    task_access = (
        Q(
            event_type__in=TASK_EVENTS,
            workspace__isnull=False,
            project__isnull=False,
            task__isnull=False,
        )
        & Q(has_workspace_access=True)
        & (
            Q(has_workspace_management=True)
            | Q(has_project_access=True)
        )
    )

    return (
        Notification.objects.filter(recipient=user)
        .annotate(
            invitation_id_text=KeyTextTransform(
                "invitation_id",
                "payload",
            ),
            has_workspace_access=Exists(workspace_membership),
            has_workspace_management=Exists(workspace_management),
            has_project_access=Exists(project_membership),
            has_active_invitation=Exists(active_invitation),
        )
        .filter(
            invitation_access
            | workspace_access
            | project_access
            | task_access
        )
        .filter(
            Q(project__isnull=True)
            | Q(project__workspace_id=F("workspace_id"))
        )
        .filter(
            Q(task__isnull=True)
            | (
                Q(project__isnull=False)
                & Q(task__project_id=F("project_id"))
            )
        )
        .order_by("-created_at", "-id")
    )
