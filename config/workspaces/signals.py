from django.conf import settings
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from workspaces.models import WorkspaceMembership


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
