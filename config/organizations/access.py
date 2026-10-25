from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from organizations.models import Organization, OrganizationMembership


def get_membership_or_404(
    slug,
    user,
    roles=None,
    *,
    for_update=False,
    permission_message=None,
):
    if for_update:
        organization_id = (
            Organization.objects
            .filter(
                slug=slug,
                memberships__user=user,
            )
            .values_list("pk", flat=True)
            .first()
        )

        if organization_id is None:
            raise Http404

        # Lock the organization without the membership join/distinct.
        organization = get_object_or_404(
            Organization.objects.select_for_update(),
            pk=organization_id,
        )

        # Lock the current user's membership separately.
        membership = get_object_or_404(
            OrganizationMembership.objects.select_for_update(),
            organization=organization,
            user=user,
        )
    else:
        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("organization"),
            organization__slug=slug,
            user=user,
        )
        organization = membership.organization

    if roles is not None and membership.role not in roles:
        raise PermissionDenied(
            permission_message
            or "You do not have permission to perform this action."
        )

    return membership
