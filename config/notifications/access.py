from django.db.models import Exists, F, OuterRef, Q
from notifications.models import Notification
from projects.models import ProjectMembership
from workspaces.models import WorkspaceMembership


def get_accessible_notifications(user):
    """
    Return notifications visible to the authenticated user.

    Invitation notifications do not require membership.

    Other workspace notifications require workspace membership.

    Project/task notifications require workspace membership
    and either project membership or workspace management access.

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

    invitation_access = Q(
        event_type=Notification.EventType.WORKSPACE_INVITED,
        workspace__isnull=False,
        project__isnull=True,
        task__isnull=True,
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
            event_type__in=[
                Notification.EventType.PROJECT_MEMBER_ADDED,
                Notification.EventType.PROJECT_ROLE_CHANGED,
                Notification.EventType.TASK_ASSIGNED,
                Notification.EventType.TASK_UPDATED,
                Notification.EventType.COMMENT_MENTIONED,
                Notification.EventType.COMMENT_REPLIED,
            ],
            workspace__isnull=False,
            project__isnull=False,
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
            has_workspace_access=Exists(workspace_membership),
            has_workspace_management=Exists(workspace_management),
            has_project_access=Exists(project_membership),
        )
        .filter(
            invitation_access
            | workspace_access
            | project_access
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
