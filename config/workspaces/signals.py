
from django.conf import settings
from django.db.models import QuerySet
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver

from projects.models import ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def prevent_deleting_workspace_owner(
    sender,
    instance,
    using,
    **kwargs,
):
    owner_memberships = (
        WorkspaceMembership.objects.using(using).filter(
            user_id=instance.pk,
            role=WorkspaceMembership.Role.OWNER,
        )
    )

    if owner_memberships.exists():
        raise ProtectedError(
            (
                "This user owns one or more workspaces. "
                "Transfer ownership before deleting the account."
            ),
            owner_memberships,
        )


@receiver(pre_delete, sender=WorkspaceMembership)
def prevent_removing_last_project_manager(
    sender,
    instance,
    using,
    origin=None,
    **kwargs,
):
    # When deleting an entire workspace, its projects are
    # deleted as well, so no manager replacement is needed.
    if isinstance(origin, Workspace):
        return

    if (
        isinstance(origin, QuerySet)
        and origin.model is Workspace
    ):
        return

    manager_memberships = (
        ProjectMembership.objects.using(using)
        .filter(
            user_id=instance.user_id,
            project__workspace_id=instance.workspace_id,
            role=ProjectMembership.Role.MANAGER,
        )
        .select_related("project")
    )

    for manager_membership in manager_memberships:
        other_manager_exists = (
            ProjectMembership.objects.using(using)
            .filter(
                project_id=manager_membership.project_id,
                role=ProjectMembership.Role.MANAGER,
                project__workspace__memberships__user_id__isnull=False,
            )
            .exclude(user_id=instance.user_id)
            .exists()
        )

        if not other_manager_exists:
            raise ProtectedError(
                (
                    "This user is the last manager of project "
                    f"'{manager_membership.project.name}'. "
                    "Assign another manager before removing "
                    "the user from the workspace."
                ),
                [manager_membership],
            )


@receiver(post_delete, sender=WorkspaceMembership)
def remove_project_memberships_after_workspace_leave(
    sender,
    instance,
    using,
    **kwargs,
):
    ProjectMembership.objects.using(using).filter(
        user_id=instance.user_id,
        project__workspace_id=instance.workspace_id,
    ).delete()
