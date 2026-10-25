from django.conf import settings
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from organizations.models import OrganizationMembership


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def prevent_deleting_organization_owner(
    sender,
    instance,
    using,
    **kwargs,
):
    owner_memberships = (
        OrganizationMembership.objects.using(using).filter(
            user_id=instance.pk,
            role=OrganizationMembership.Role.OWNER,
        )
    )

    if owner_memberships.exists():
        raise ProtectedError(
            (
                "This user owns one or more organizations. "
                "Transfer ownership before deleting the account."
            ),
            owner_memberships,
        )
