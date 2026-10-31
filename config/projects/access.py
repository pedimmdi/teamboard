
from dataclasses import dataclass
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from projects.models import Project, ProjectMembership
from workspaces.models import WorkspaceMembership


@dataclass(frozen=True)
class ProjectManagementAccess:
    project: Project
    role: str = ProjectMembership.Role.MANAGER

    @property
    def project_id(self):
        return self.project.pk


def get_project_membership_or_404(
    *,
    project_id,
    user,
    roles=None,
):
    privileged_project = Project.objects.filter(
        pk=project_id, workspace__memberships__user=user,
        workspace__memberships__role__in=["owner", "admin"],
    ).first()
    if privileged_project is not None:
        return ProjectManagementAccess(project=privileged_project)
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
    get_object_or_404(Project, pk=project_id, workspace__slug=workspace_slug)
    return get_project_membership_or_404(project_id=project_id, user=user, roles=roles)
