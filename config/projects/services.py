from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied

from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


@transaction.atomic
def create_project(*, workspace, created_by, name, description=""):
    # Serialize project creation against workspace membership changes.
    workspace = Workspace.objects.select_for_update().get(
        pk=workspace.pk,
    )

    if not WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=created_by,
        role__in=[
            WorkspaceMembership.Role.OWNER,
            WorkspaceMembership.Role.ADMIN,
        ],
    ).exists():
        raise PermissionDenied(
            "Only workspace owners and admins can create projects."
        )

    name = name.strip()
    if not name:
        raise ValidationError({
            "name": "Project name cannot be empty."
        })

    if len(name) > 150:
        raise ValidationError({
            "name": "Project name cannot exceed 150 characters."
        })

    if Project.objects.filter(
        workspace=workspace,
        name__iexact=name,
    ).exists():
        raise ValidationError({
            "name": "A project with this name already exists."
        })

    project = Project.objects.create(
        workspace=workspace,
        name=name,
        description=description,
        created_by=created_by,
    )

    ProjectMembership.objects.create(
        project=project,
        user=created_by,
        role=ProjectMembership.Role.MANAGER,
    )

    return project


@transaction.atomic
def add_project_member(
    *,
    project,
    actor,
    user,
    role=ProjectMembership.Role.MEMBER,
):
    workspace = Workspace.objects.select_for_update().get(
        pk=project.workspace_id,
    )
    project = Project.objects.select_for_update().get(
        pk=project.pk,
        workspace=workspace,
    )

    actor_membership = ProjectMembership.objects.filter(
        project=project,
        user=actor,
        project__workspace__memberships__user=actor,
    ).first()

    if actor_membership is None:
        raise PermissionDenied(
            "You are not a member of this project."
        )

    if actor_membership.role != ProjectMembership.Role.MANAGER:
        raise PermissionDenied(
            "Only project managers can add members."
        )

    if not WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=user,
    ).exists():
        raise ValidationError({
            "user": "User must belong to the project's workspace."
        })

    if role not in ProjectMembership.Role.values:
        raise ValidationError({
            "role": "Invalid project role."
        })

    if role == ProjectMembership.Role.MANAGER:
        if not WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=actor,
            role__in=[
                WorkspaceMembership.Role.OWNER,
                WorkspaceMembership.Role.ADMIN,
            ],
        ).exists():
            raise PermissionDenied(
                "Only workspace owners and admins can assign managers."
            )

    if ProjectMembership.objects.filter(
        project=project,
        user=user,
    ).exists():
        raise ValidationError({
            "user": "User is already a project member."
        })

    return ProjectMembership.objects.create(
        project=project,
        user=user,
        role=role,
    )


@transaction.atomic
def change_project_member_role(
    *,
    project,
    actor,
    membership_id,
    role,
):
    workspace = Workspace.objects.select_for_update().get(
        pk=project.workspace_id,
    )
    project = Project.objects.select_for_update().get(
        pk=project.pk,
        workspace=workspace,
    )

    if not WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=actor,
        role__in=[
            WorkspaceMembership.Role.OWNER,
            WorkspaceMembership.Role.ADMIN,
        ],
    ).exists():
        raise PermissionDenied(
            "Only workspace owners and admins can change project roles."
        )

    if not ProjectMembership.objects.filter(
        project=project,
        user=actor,
    ).exists():
        raise PermissionDenied(
            "You must be a project member."
        )

    if role not in ProjectMembership.Role.values:
        raise ValidationError({
            "role": "Invalid project role."
        })

    membership = get_object_or_404(
        ProjectMembership.objects.select_for_update(),
        pk=membership_id,
        project=project,
    )

    if membership.role == role:
        return membership

    if (
        membership.role == ProjectMembership.Role.MANAGER
        and role == ProjectMembership.Role.MEMBER
        and not ProjectMembership.objects.filter(
            project=project,
            role=ProjectMembership.Role.MANAGER,
        ).exclude(pk=membership.pk).exists()
    ):
        raise ValidationError({
            "role": "A project must have at least one manager."
        })

    membership.role = role
    membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def remove_project_member(
    *,
    project,
    actor,
    membership_id,
):
    workspace = Workspace.objects.select_for_update().get(
        pk=project.workspace_id,
    )
    project = Project.objects.select_for_update().get(
        pk=project.pk,
        workspace=workspace,
    )

    actor_membership = ProjectMembership.objects.filter(
        project=project,
        user=actor,
        project__workspace__memberships__user=actor,
    ).first()

    if (
        actor_membership is None
        or actor_membership.role != ProjectMembership.Role.MANAGER
    ):
        raise PermissionDenied(
            "Only project managers can remove members."
        )

    membership = get_object_or_404(
        ProjectMembership.objects.select_for_update(),
        pk=membership_id,
        project=project,
    )

    if membership.role == ProjectMembership.Role.MANAGER:
        raise PermissionDenied(
            "Managers cannot remove other project managers. "
            "Workspace owners and admins must manage manager roles."
        )

    membership.delete()
