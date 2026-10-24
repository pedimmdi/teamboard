from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from organizations.services import (
    create_organization_invitation,
    accept_organization_invitation
)
from .serializers import (
    OrganizationSerializer,
    OrganizationInvitationCreateSerializer,
    OrganizationInvitationSerializer,
    OrganizationInvitationAcceptSerializer,
    OrganizationMembershipSerializer,
    OrganizationMembershipRoleUpdateSerializer,
)


class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Organization.objects.filter(
                memberships__user=self.request.user,
            )
            .order_by("name")
            .distinct()
        )


class OrganizationDetailView(generics.RetrieveAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
        )


INVITATION_MANAGEMENT_ROLES = (
    OrganizationMembership.Role.OWNER,
    OrganizationMembership.Role.ADMIN,
)


class OrganizationInvitationAccessMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_organization_and_membership(self):
        organization = get_object_or_404(
            Organization.objects.filter(
                memberships__user=self.request.user,
            ).distinct(),
            slug=self.kwargs["slug"],
        )

        membership = get_object_or_404(
            OrganizationMembership,
            organization=organization,
            user=self.request.user,
        )

        if membership.role not in INVITATION_MANAGEMENT_ROLES:
            raise PermissionDenied(
                "Only organization owners and admins can manage invitations."
            )

        return organization, membership


class OrganizationInvitationListCreateView(
    OrganizationInvitationAccessMixin,
    generics.ListCreateAPIView,
):
    def get_queryset(self):
        organization, _ = self.get_organization_and_membership()

        return OrganizationInvitation.objects.filter(
            organization=organization,
        ).select_related("invited_by", "organization")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrganizationInvitationCreateSerializer

        return OrganizationInvitationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization, _ = self.get_organization_and_membership()

        try:
            invitation = create_organization_invitation(
                organization=organization,
                invited_by=request.user,
                email=serializer.validated_data["email"],
            )
        except IntegrityError as exc:
            raise ValidationError({
                "email": "An active invitation already exists for this email."
            }) from exc

        output = OrganizationInvitationSerializer(invitation)

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationInvitationRevokeView(
    OrganizationInvitationAccessMixin,
    APIView,
):
    def delete(self, request, slug, invitation_id):
        organization, _ = self.get_organization_and_membership()

        with transaction.atomic():
            invitation = get_object_or_404(
                OrganizationInvitation.objects.select_for_update(),
                id=invitation_id,
                organization=organization,
            )

            if invitation.status != OrganizationInvitation.Status.PENDING:
                raise ValidationError({
                    "status": "Only pending invitations can be revoked."
                })

            if invitation.expires_at <= timezone.now():
                invitation.status = OrganizationInvitation.Status.EXPIRED
                invitation.save(update_fields=["status"])
                expired = True
            else:
                invitation.status = OrganizationInvitation.Status.REVOKED
                invitation.revoked_at = timezone.now()
                invitation.save(update_fields=["status", "revoked_at"])
                expired = False

        if expired:
            raise ValidationError({
                "status": "This invitation has expired."
            })

        return Response(
            {"detail": "Invitation revoked successfully."},
            status=status.HTTP_200_OK,
        )


class OrganizationInvitationAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = OrganizationInvitationAcceptSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        invitation = accept_organization_invitation(
            token=serializer.validated_data["token"],
            user=request.user,
        )

        return Response(
            {
                "detail": "Invitation accepted successfully.",
                "organization": {
                    "id": str(invitation.organization.id),
                    "name": invitation.organization.name,
                    "slug": invitation.organization.slug,
                },
                "role": OrganizationMembership.Role.MEMBER,
            },
            status=status.HTTP_200_OK,
        )


class OrganizationMemberListView(
    OrganizationInvitationAccessMixin,
    generics.ListAPIView,
):
    serializer_class = OrganizationMembershipSerializer

    def get_organization_and_membership(self):
        organization = get_object_or_404(
            Organization.objects.filter(
                memberships__user=self.request.user,
            ).distinct(),
            slug=self.kwargs["slug"],
        )

        membership = get_object_or_404(
            OrganizationMembership,
            organization=organization,
            user=self.request.user,
        )

        return organization, membership

    def get_queryset(self):
        organization, _ = self.get_organization_and_membership()

        return (
            OrganizationMembership.objects
            .filter(organization=organization)
            .select_related("user")
            .order_by("joined_at")
        )


class OrganizationMemberRoleUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, slug, membership_id):
        serializer = OrganizationMembershipRoleUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            organization = get_object_or_404(
                Organization.objects.select_for_update(),
                slug=slug,
                memberships__user=request.user,
            )

            # Lock and verify the requesting user's membership.
            actor_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                user=request.user,
            )

            if actor_membership.role != OrganizationMembership.Role.OWNER:
                raise PermissionDenied(
                    "Only the organization owner can change member roles."
                )

            target_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                id=membership_id,
            )

            if target_membership.role == OrganizationMembership.Role.OWNER:
                raise ValidationError({
                    "role": (
                        "The owner's role cannot be changed "
                        "through this endpoint."
                    )
                })

            target_membership.role = serializer.validated_data["role"]
            target_membership.save(update_fields=["role"])

        return Response(
            OrganizationMembershipSerializer(target_membership).data,
            status=status.HTTP_200_OK,
        )
