from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

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
    OrganizationOwnershipTransferSerializer,
)


@extend_schema_view(
    get=extend_schema(
        tags=["Organizations"],
        summary="List organizations",
        description=(
            "Returns all organizations that the authenticated user "
            "is a member of."
        ),
        responses={
            200: OrganizationSerializer(many=True),
        },
    ),
    post=extend_schema(
        tags=["Organizations"],
        summary="Create organization",
        description=(
            "Creates a new organization. The authenticated user "
            "automatically becomes the organization owner."
        ),
        request=OrganizationSerializer,
        responses={
            201: OrganizationSerializer,
        },
    ),
)
class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "organization_create"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        current_user_memberships = OrganizationMembership.objects.filter(
            user=self.request.user,
        )

        return (
            Organization.objects.filter(
                memberships__user=self.request.user,
            )
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=current_user_memberships,
                    to_attr="current_user_memberships",
                )
            )
            .order_by("name")
            .distinct()
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Organizations"],
        summary="Retrieve organization",
        description=(
            "Returns the details of an organization that the "
            "authenticated user belongs to."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        responses={
            200: OrganizationSerializer,
            404: OpenApiResponse(
                description="Organization not found.",
            ),
        },
    ),
    patch=extend_schema(
        tags=["Organizations"],
        summary="Update organization",
        description=(
            "Updates an organization's editable fields. "
            "Only organization owners and admins can perform this operation."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        request=OrganizationSerializer,
        responses={
            200: OrganizationSerializer,
            403: OpenApiResponse(
                description="The authenticated user does not have permission to update the organization.",
            ),
            404: OpenApiResponse(
                description="Organization not found.",
            ),
        },
    ),
    delete=extend_schema(
        tags=["Organizations"],
        summary="Delete organization",
        description=(
            "Permanently deletes the organization and its related "
            "memberships and invitations. Only the organization owner "
            "can perform this operation."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        responses={
            204: OpenApiResponse(
                description="Organization deleted successfully.",
            ),
            403: OpenApiResponse(
                description="Only the organization owner can delete the organization.",
            ),
            404: OpenApiResponse(
                description="Organization not found.",
            ),
        },
    ),
)
class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationSerializer
    lookup_field = "slug"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        current_user_memberships = OrganizationMembership.objects.filter(
            user=self.request.user,
        )

        return (
            Organization.objects.filter(
                memberships__user=self.request.user,
            )
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=current_user_memberships,
                    to_attr="current_user_memberships",
                )
            )
            .distinct()
        )

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            organization = get_object_or_404(
                Organization.objects.select_for_update(),
                slug=kwargs["slug"],
            )

            membership = (
                OrganizationMembership.objects
                .select_for_update()
                .filter(
                    organization=organization,
                    user=request.user,
                )
                .first()
            )

            if membership is None:
                raise NotFound("Organization not found.")

            if membership.role not in {
                OrganizationMembership.Role.OWNER,
                OrganizationMembership.Role.ADMIN,
            }:
                raise PermissionDenied(
                    "Only organization owners and admins can update the organization."
                )

            serializer = self.get_serializer(
                organization,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

        return Response(serializer.data)

    def perform_destroy(self, instance):
        with transaction.atomic():
            organization = (
                Organization.objects
                .select_for_update()
                .get(pk=instance.pk)
            )

            membership = (
                OrganizationMembership.objects
                .select_for_update()
                .filter(
                    organization=organization,
                    user=self.request.user,
                )
                .first()
            )

            if membership is None:
                raise NotFound("Organization not found.")

            if membership.role != OrganizationMembership.Role.OWNER:
                raise PermissionDenied(
                    "Only the organization owner can delete the organization."
                )

            organization.delete()

        return None


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


@extend_schema_view(
    get=extend_schema(
        tags=["Organizations - Invitations"],
        summary="List organization invitations",
        description=(
            "Returns invitations for an organization. "
            "Only organization owners and admins can manage invitations."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        responses={
            200: OrganizationInvitationSerializer(many=True),
        },
    ),
    post=extend_schema(
        tags=["Organizations - Invitations"],
        summary="Create organization invitation",
        description=(
            "Creates an invitation for an email address. "
            "Only organization owners and admins can invite users."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        request=OrganizationInvitationCreateSerializer,
        responses={
            201: OrganizationInvitationSerializer,
            400: OpenApiResponse(
                description="Invalid email, existing member, or active invitation.",
            ),
            403: OpenApiResponse(
                description="The authenticated user cannot manage invitations.",
            ),
            404: OpenApiResponse(
                description="Organization not found.",
            ),
        },
    ),
)
class OrganizationInvitationListCreateView(
    OrganizationInvitationAccessMixin,
    generics.ListCreateAPIView,
):
    throttle_scope = "organization_invitation"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

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


@extend_schema_view(
    delete=extend_schema(
        tags=["Organizations - Invitations"],
        summary="Revoke organization invitation",
        description=(
            "Revokes a pending invitation. "
            "Only organization owners and admins can revoke invitations."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
            OpenApiParameter(
                name="invitation_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="The UUID of the invitation.",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Invitation revoked successfully.",
            ),
            400: OpenApiResponse(
                description="The invitation is not pending or has already expired.",
            ),
            403: OpenApiResponse(
                description="The authenticated user cannot manage invitations.",
            ),
            404: OpenApiResponse(
                description="Organization or invitation not found.",
            ),
        },
    ),
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


@extend_schema(
    tags=["Organizations - Invitations"],
    summary="Accept organization invitation",
    description=(
        "Accepts an organization invitation using its token and adds "
        "the authenticated user as a member of the organization."
    ),
    request=OrganizationInvitationAcceptSerializer,
    responses={
        200: OpenApiResponse(
            description="Invitation accepted successfully.",
        ),
        400: OpenApiResponse(
            description="Invalid, expired, revoked, or otherwise unusable invitation.",
        ),
        401: OpenApiResponse(
            description="Authentication is required.",
        ),
    },
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


@extend_schema_view(
    get=extend_schema(
        tags=["Organizations - Members"],
        summary="List organization members",
        description=(
            "Returns all members of the organization. "
            "Any authenticated member of the organization can view the list."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the organization.",
            ),
        ],
        responses={
            200: OrganizationMembershipSerializer(many=True),
        },
    ),
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


@extend_schema(
    tags=["Organizations - Members"],
    summary="Update member role",
    description=(
        "Changes an organization's member role between admin and member. "
        "Only the organization owner can change member roles. "
        "The owner's role cannot be changed through this endpoint."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the organization.",
        ),
        OpenApiParameter(
            name="membership_id",
            type=str,
            location=OpenApiParameter.PATH,
            description="The UUID of the membership.",
        ),
    ],
    request=OrganizationMembershipRoleUpdateSerializer,
    responses={
        200: OrganizationMembershipSerializer,
        400: OpenApiResponse(
            description="Invalid role or attempt to change the owner's role.",
        ),
        403: OpenApiResponse(
            description="Only the organization owner can change member roles.",
        ),
        404: OpenApiResponse(
            description="Organization or membership not found.",
        ),
    },
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
            OrganizationMembershipSerializer(
                target_membership,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Organizations - Members"],
    summary="Remove organization member",
    description=(
        "Removes a member from the organization without deleting "
        "the user's account. Owners can remove admins and members; "
        "admins can remove members only."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the organization.",
        ),
        OpenApiParameter(
            name="membership_id",
            type=str,
            location=OpenApiParameter.PATH,
            description="The UUID of the membership to remove.",
        ),
    ],
    responses={
        204: OpenApiResponse(
            description="Member removed successfully.",
        ),
        400: OpenApiResponse(
            description="The organization owner cannot be removed.",
        ),
        403: OpenApiResponse(
            description="The authenticated user does not have permission to remove this member.",
        ),
        404: OpenApiResponse(
            description="Organization or membership not found.",
        ),
    },
)
class OrganizationMemberRemoveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, slug, membership_id):
        with transaction.atomic():
            organization = get_object_or_404(
                Organization.objects.select_for_update(),
                slug=slug,
                memberships__user=request.user,
            )

            actor_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                user=request.user,
            )

            if actor_membership.role not in (
                OrganizationMembership.Role.OWNER,
                OrganizationMembership.Role.ADMIN,
            ):
                raise PermissionDenied(
                    "Only organization owners and admins can remove members."
                )

            target_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                id=membership_id,
            )

            if target_membership.role == OrganizationMembership.Role.OWNER:
                raise ValidationError({
                    "membership_id": (
                        "The organization owner cannot be removed "
                        "through this endpoint."
                    )
                })

            if (
                actor_membership.role == OrganizationMembership.Role.ADMIN
                and target_membership.role != OrganizationMembership.Role.MEMBER
            ):
                raise PermissionDenied(
                    "Admins can remove members only, not other admins."
                )

            target_membership.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Organizations - Members"],
    summary="Transfer organization ownership",
    description=(
        "Transfers organization ownership to another member. "
        "The current owner becomes an admin and the selected member "
        "becomes the new owner."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the organization.",
        ),
    ],
    request=OrganizationOwnershipTransferSerializer,
    responses={
        200: OrganizationMembershipSerializer,
        400: OpenApiResponse(
            description="Invalid membership or ownership transfer request.",
        ),
        403: OpenApiResponse(
            description="Only the organization owner can transfer ownership.",
        ),
        404: OpenApiResponse(
            description="Organization or target membership not found.",
        ),
    },
)
class OrganizationOwnershipTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        serializer = OrganizationOwnershipTransferSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        membership_id = serializer.validated_data["membership_id"]

        with transaction.atomic():
            organization = get_object_or_404(
                Organization.objects.select_for_update(),
                slug=slug,
                memberships__user=request.user,
            )

            actor_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                user=request.user,
            )

            if actor_membership.role != OrganizationMembership.Role.OWNER:
                raise PermissionDenied(
                    "Only the organization owner can transfer ownership."
                )

            target_membership = get_object_or_404(
                OrganizationMembership.objects.select_for_update(),
                organization=organization,
                id=membership_id,
            )

            if target_membership.id == actor_membership.id:
                raise ValidationError({
                    "membership_id": (
                        "You cannot transfer ownership to yourself."
                    )
                })

            actor_membership.role = OrganizationMembership.Role.ADMIN
            actor_membership.save(update_fields=["role"])

            target_membership.role = OrganizationMembership.Role.OWNER
            target_membership.save(update_fields=["role"])

        return Response(
            OrganizationMembershipSerializer(target_membership).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Organizations - Members"],
    summary="Leave organization",
    description=(
        "Removes the authenticated user's membership from the organization. "
        "Organization owners cannot leave directly; they must transfer "
        "ownership or delete the organization."
    ),
    request=None,
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the organization.",
        ),
    ],
    responses={
        204: OpenApiResponse(
            description="Successfully left the organization.",
        ),
        400: OpenApiResponse(
            description="Organization owners cannot leave the organization.",
        ),
        404: OpenApiResponse(
            description="Organization or membership not found.",
        ),
    },
)
class OrganizationLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        with transaction.atomic():
            organization = (
                Organization.objects
                .select_for_update()
                .filter(slug=slug)
                .first()
            )

            if organization is None:
                raise NotFound("Organization not found.")

            membership = (
                OrganizationMembership.objects
                .select_for_update()
                .filter(
                    organization=organization,
                    user=request.user,
                )
                .first()
            )

            if membership is None:
                raise NotFound("Organization not found.")

            if membership.role == OrganizationMembership.Role.OWNER:
                raise ValidationError(
                    "Organization owners cannot leave the organization. "
                    "Transfer ownership or delete the organization instead."
                )

            membership.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
