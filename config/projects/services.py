from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied

from projects.models import Project, ProjectMembership
from projects.access import get_project_membership_or_404
from workspaces.models import Workspace, WorkspaceMembership


def has_other_project_manager(*, project, excluded_membership_id):
    eligible_user_ids = WorkspaceMembership.objects.filter(
        workspace_id=project.workspace_id,
    ).values("user_id")

    return ProjectMembership.objects.filter(
        project=project,
        role=ProjectMembership.Role.MANAGER,
        user_id__in=eligible_user_ids,
    ).exclude(
        pk=excluded_membership_id,
    ).exists()


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
    if len(description) > 5000:
        raise ValidationError({"description": "Description cannot exceed 5000 characters."})
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

    get_project_membership_or_404(
        project_id=project.pk, user=actor, roles={ProjectMembership.Role.MANAGER},
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
        and not has_other_project_manager(
            project=project,
            excluded_membership_id=membership.pk,
        )
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

    get_project_membership_or_404(
        project_id=project.pk, user=actor, roles={ProjectMembership.Role.MANAGER},
    )

    membership = get_object_or_404(
        ProjectMembership.objects.select_for_update(),
        pk=membership_id,
        project=project,
    )

    privileged = WorkspaceMembership.objects.filter(
        workspace=workspace, user=actor, role__in=["owner", "admin"],
    ).exists()
    if membership.role == ProjectMembership.Role.MANAGER and not privileged:
        raise PermissionDenied(
            "Managers cannot remove other project managers. "
            "Workspace owners and admins must manage manager roles."
        )

    if membership.role == ProjectMembership.Role.MANAGER and not has_other_project_manager(
        project=project, excluded_membership_id=membership.pk,
    ):
        raise ValidationError({"detail": "Assign another manager before removing this project manager."})

    membership.delete()


@transaction.atomic
def delete_project(*, project, actor):
    workspace = Workspace.objects.select_for_update().get(
        pk=project.workspace_id,
    )

    project = get_object_or_404(
        Project.objects.select_for_update(),
        pk=project.pk,
        workspace=workspace,
    )

    workspace_permission = WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=actor,
        role__in=[
            WorkspaceMembership.Role.OWNER,
            WorkspaceMembership.Role.ADMIN,
        ],
    ).exists()

    if not workspace_permission:
        raise PermissionDenied(
            "Only workspace owners and admins can delete projects."
        )

    project.delete()


@transaction.atomic
def leave_project(*, project, actor):
    workspace = Workspace.objects.select_for_update().get(
        pk=project.workspace_id,
    )

    project = get_object_or_404(
        Project.objects.select_for_update(),
        pk=project.pk,
        workspace=workspace,
    )

    membership = get_object_or_404(
        ProjectMembership.objects.select_for_update(),
        project=project,
        user=actor,
        project__workspace__memberships__user=actor,
    )

    if membership.role == ProjectMembership.Role.MANAGER:
        other_manager_exists = has_other_project_manager(
            project=project,
            excluded_membership_id=membership.pk,
        )

        if not other_manager_exists:
            raise ValidationError({
                "detail": "A project must have at least one manager."
            })

    membership.delete()
