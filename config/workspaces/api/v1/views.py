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
from workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from workspaces.services import (
    create_workspace_invitation,
    accept_workspace_invitation,
    resend_workspace_invitation,
)
from .serializers import (
    WorkspaceSerializer,
    WorkspaceInvitationCreateSerializer,
    WorkspaceInvitationSerializer,
    WorkspaceInvitationAcceptSerializer,
    WorkspaceMembershipSerializer,
    WorkspaceMembershipRoleUpdateSerializer,
    WorkspaceOwnershipTransferSerializer,
    PaginatedWorkspaceSerializer,
    PaginatedWorkspaceMembershipSerializer,
    PaginatedWorkspaceInvitationSerializer,
)
from workspaces.access import get_membership_or_404
from .pagination import WorkspacePageNumberPagination


@extend_schema_view(
    get=extend_schema(
        tags=["Workspaces"],
        summary="List workspaces",
        description=(
            "Returns all workspaces that the authenticated user "
            "is a member of."
        ),
        responses={
            200: PaginatedWorkspaceSerializer
        },
    ),
    post=extend_schema(
        tags=["Workspaces"],
        summary="Create workspace",
        description=(
            "Creates a new workspace. The authenticated user "
            "automatically becomes the workspace owner."
        ),
        request=WorkspaceSerializer,
        responses={
            201: WorkspaceSerializer,
        },
    ),
)
class WorkspaceListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = WorkspacePageNumberPagination
    throttle_scope = "workspace_create"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        current_user_memberships = WorkspaceMembership.objects.filter(
            user=self.request.user,
        )

        return (
            Workspace.objects.filter(
                memberships__user=self.request.user,
            )
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=current_user_memberships,
                    to_attr="current_user_memberships",
                )
            )
            .order_by("name", "pk")
            .distinct()
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Workspaces"],
        summary="Retrieve workspace",
        description=(
            "Returns the details of an workspace that the "
            "authenticated user belongs to."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        responses={
            200: WorkspaceSerializer,
            404: OpenApiResponse(
                description="Workspace not found.",
            ),
        },
    ),
    patch=extend_schema(
        tags=["Workspaces"],
        summary="Update workspace",
        description=(
            "Updates an workspace's editable fields. "
            "Only workspace owners and admins can perform this operation."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        request=WorkspaceSerializer,
        responses={
            200: WorkspaceSerializer,
            403: OpenApiResponse(
                description="The authenticated user does not have permission to update the workspace.",
            ),
            404: OpenApiResponse(
                description="Workspace not found.",
            ),
        },
    ),
    delete=extend_schema(
        tags=["Workspaces"],
        summary="Delete workspace",
        description=(
            "Permanently deletes the workspace and its related "
            "memberships and invitations. Only the workspace owner "
            "can perform this operation."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        responses={
            204: OpenApiResponse(
                description="Workspace deleted successfully.",
            ),
            403: OpenApiResponse(
                description="Only the workspace owner can delete the workspace.",
            ),
            404: OpenApiResponse(
                description="Workspace not found.",
            ),
        },
    ),
)
class WorkspaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkspaceSerializer
    lookup_field = "slug"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        current_user_memberships = WorkspaceMembership.objects.filter(
            user=self.request.user,
        )

        return (
            Workspace.objects.filter(
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
            membership = get_membership_or_404(
                slug=kwargs["slug"],
                user=request.user,
                roles={
                    WorkspaceMembership.Role.OWNER,
                    WorkspaceMembership.Role.ADMIN,
                },
                for_update=True,
                permission_message=(
                    "Only workspace owners and admins can update "
                    "the workspace."
                ),
            )
            workspace = membership.workspace

            serializer = self.get_serializer(
                workspace,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

        return Response(serializer.data)

    def perform_destroy(self, instance):
        with transaction.atomic():
            membership = get_membership_or_404(
                slug=instance.slug,
                user=self.request.user,
                roles={WorkspaceMembership.Role.OWNER},
                for_update=True,
                permission_message=(
                    "Only the workspace owner can delete "
                    "the workspace."
                ),
            )

            membership.workspace.delete()

        return None


INVITATION_MANAGEMENT_ROLES = (
    WorkspaceMembership.Role.OWNER,
    WorkspaceMembership.Role.ADMIN,
)

class WorkspaceInvitationAccessMixin:
    permission_classes = [permissions.IsAuthenticated]

    def get_workspace_and_membership(self):
        membership = get_membership_or_404(
            slug=self.kwargs["slug"],
            user=self.request.user,
            roles=INVITATION_MANAGEMENT_ROLES,
            permission_message=(
                "Only workspace owners and admins can manage invitations."
            ),
        )

        return membership.workspace, membership


@extend_schema_view(
    get=extend_schema(
        tags=["Workspaces - Invitations"],
        summary="List workspace invitations",
        description=(
            "Returns invitations for an workspace. "
            "Only workspace owners and admins can manage invitations."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        responses={
            200: PaginatedWorkspaceInvitationSerializer,
        },
    ),
    post=extend_schema(
        tags=["Workspaces - Invitations"],
        summary="Create workspace invitation",
        description=(
            "Creates an invitation for an email address. "
            "Only workspace owners and admins can invite users."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        request=WorkspaceInvitationCreateSerializer,
        responses={
            201: WorkspaceInvitationSerializer,
            400: OpenApiResponse(
                description="Invalid email, existing member, or active invitation.",
            ),
            403: OpenApiResponse(
                description="The authenticated user cannot manage invitations.",
            ),
            404: OpenApiResponse(
                description="Workspace not found.",
            ),
        },
    ),
)
class WorkspaceInvitationListCreateView(
    WorkspaceInvitationAccessMixin,
    generics.ListCreateAPIView,
):
    pagination_class = WorkspacePageNumberPagination
    throttle_scope = "workspace_invitation"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        workspace, _ = self.get_workspace_and_membership()

        return (
            WorkspaceInvitation.objects
            .filter(workspace=workspace)
            .select_related("invited_by", "workspace")
            .order_by("-created_at", "-pk")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WorkspaceInvitationCreateSerializer

        return WorkspaceInvitationSerializer

    def create(self, request, *args, **kwargs):
        # Check workspace membership and invitation permissions first.
        workspace, _ = self.get_workspace_and_membership()

        # Validate the request only after access has been confirmed.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = create_workspace_invitation(
                workspace=workspace,
                invited_by=request.user,
                email=serializer.validated_data["email"],
            )
        except IntegrityError as exc:
            raise ValidationError({
                "email": "An active invitation already exists for this email."
            }) from exc

        output = WorkspaceInvitationSerializer(invitation)

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    delete=extend_schema(
        tags=["Workspaces - Invitations"],
        summary="Revoke workspace invitation",
        description=(
            "Revokes a pending invitation. "
            "Only workspace owners and admins can revoke invitations."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
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
                description="Workspace or invitation not found.",
            ),
        },
    ),
)
class WorkspaceInvitationRevokeView(
    WorkspaceInvitationAccessMixin,
    APIView,
):
    def delete(self, request, slug, invitation_id):
        workspace, _ = self.get_workspace_and_membership()

        with transaction.atomic():
            invitation = get_object_or_404(
                WorkspaceInvitation.objects.select_for_update(),
                id=invitation_id,
                workspace=workspace,
            )

            if invitation.status != WorkspaceInvitation.Status.PENDING:
                raise ValidationError({
                    "status": "Only pending invitations can be revoked."
                })

            if invitation.expires_at <= timezone.now():
                invitation.status = WorkspaceInvitation.Status.EXPIRED
                invitation.save(update_fields=["status"])
                expired = True
            else:
                invitation.status = WorkspaceInvitation.Status.REVOKED
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
    tags=["Workspaces - Invitations"],
    summary="Resend workspace invitation",
    description=(
        "Resends an invitation email with a newly generated token "
        "and renews its expiration date. Only workspace owners "
        "and admins can resend invitations."
    ),
    responses={
        200: WorkspaceInvitationSerializer,
        400: OpenApiResponse(
            description=(
                "The invitation was accepted, revoked, or cannot be resent."
            ),
        ),
        403: OpenApiResponse(
            description="The authenticated user cannot manage invitations.",
        ),
        404: OpenApiResponse(
            description="The workspace or invitation was not found.",
        ),
        429: OpenApiResponse(
            description="The invitation rate limit was exceeded.",
        ),
    },
)
class WorkspaceInvitationResendView(
    WorkspaceInvitationAccessMixin,
    APIView,
):
    serializer_class = WorkspaceInvitationSerializer
    throttle_scope = "workspace_invitation"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def post(self, request, slug, invitation_id):
        # Verify membership and permissions before accessing the invitation.
        workspace, _ = self.get_workspace_and_membership()

        invitation = resend_workspace_invitation(
            workspace=workspace,
            invitation_id=invitation_id,
            invited_by=request.user,
        )

        return Response(
            WorkspaceInvitationSerializer(invitation).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Workspaces - Invitations"],
    summary="Accept workspace invitation",
    description=(
        "Accepts an workspace invitation using its token and adds "
        "the authenticated user as a member of the workspace."
    ),
    request=WorkspaceInvitationAcceptSerializer,
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
class WorkspaceInvitationAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WorkspaceInvitationAcceptSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        invitation = accept_workspace_invitation(
            token=serializer.validated_data["token"],
            user=request.user,
        )

        return Response(
            {
                "detail": "Invitation accepted successfully.",
                "workspace": {
                    "id": str(invitation.workspace.id),
                    "name": invitation.workspace.name,
                    "slug": invitation.workspace.slug,
                },
                "role": WorkspaceMembership.Role.MEMBER,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Workspaces - Members"],
        summary="List workspace members",
        description=(
            "Returns all members of the workspace. "
            "Any authenticated member of the workspace can view the list."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                type=str,
                location=OpenApiParameter.PATH,
                description="The unique slug of the workspace.",
            ),
        ],
        responses={
            200: PaginatedWorkspaceMembershipSerializer,
        },
    ),
)
class WorkspaceMemberListView(
    WorkspaceInvitationAccessMixin,
    generics.ListAPIView,
):
    serializer_class = WorkspaceMembershipSerializer
    pagination_class = WorkspacePageNumberPagination

    def get_workspace_and_membership(self):
        membership = get_membership_or_404(
            slug=self.kwargs["slug"],
            user=self.request.user,
        )

        return membership.workspace, membership

    def get_queryset(self):
        workspace, _ = self.get_workspace_and_membership()

        return (
            WorkspaceMembership.objects
            .filter(workspace=workspace)
            .select_related("user__profile")
            .order_by("joined_at", "pk")
        )


@extend_schema(
    tags=["Workspaces - Members"],
    summary="Update member role",
    description=(
        "Changes an workspace's member role between admin and member. "
        "Only the workspace owner can change member roles. "
        "The owner's role cannot be changed through this endpoint."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the workspace.",
        ),
        OpenApiParameter(
            name="membership_id",
            type=str,
            location=OpenApiParameter.PATH,
            description="The UUID of the membership.",
        ),
    ],
    request=WorkspaceMembershipRoleUpdateSerializer,
    responses={
        200: WorkspaceMembershipSerializer,
        400: OpenApiResponse(
            description="Invalid role or attempt to change the owner's role.",
        ),
        403: OpenApiResponse(
            description="Only the workspace owner can change member roles.",
        ),
        404: OpenApiResponse(
            description="Workspace or membership not found.",
        ),
    },
)
class WorkspaceMemberRoleUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, slug, membership_id):
        with transaction.atomic():
            actor_membership = get_membership_or_404(
                slug=slug,
                user=request.user,
                roles={WorkspaceMembership.Role.OWNER},
                for_update=True,
                permission_message=(
                    "Only the workspace owner can change member roles."
                ),
            )
            workspace = actor_membership.workspace

            # Validate only after verifying the actor's permissions.
            serializer = WorkspaceMembershipRoleUpdateSerializer(
                data=request.data,
            )
            serializer.is_valid(raise_exception=True)

            target_membership = get_object_or_404(
                WorkspaceMembership.objects.select_for_update(),
                workspace=workspace,
                id=membership_id,
            )

            if target_membership.role == WorkspaceMembership.Role.OWNER:
                raise ValidationError({
                    "role": (
                        "The owner's role cannot be changed "
                        "through this endpoint."
                    )
                })

            target_membership.role = serializer.validated_data["role"]
            target_membership.save(update_fields=["role"])

        return Response(
            WorkspaceMembershipSerializer(
                target_membership,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Workspaces - Members"],
    summary="Remove workspace member",
    description=(
        "Removes a member from the workspace without deleting "
        "the user's account. Owners can remove admins and members; "
        "admins can remove members only."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the workspace.",
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
            description="The workspace owner cannot be removed.",
        ),
        403: OpenApiResponse(
            description="The authenticated user does not have permission to remove this member.",
        ),
        404: OpenApiResponse(
            description="Workspace or membership not found.",
        ),
    },
)
class WorkspaceMemberRemoveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, slug, membership_id):
        with transaction.atomic():
            actor_membership = get_membership_or_404(
                slug=slug,
                user=request.user,
                roles={
                    WorkspaceMembership.Role.OWNER,
                    WorkspaceMembership.Role.ADMIN,
                },
                for_update=True,
                permission_message=(
                    "Only workspace owners and admins can remove members."
                ),
            )
            workspace = actor_membership.workspace

            target_membership = get_object_or_404(
                WorkspaceMembership.objects.select_for_update(),
                workspace=workspace,
                id=membership_id,
            )

            if target_membership.role == WorkspaceMembership.Role.OWNER:
                raise ValidationError({
                    "membership_id": (
                        "The workspace owner cannot be removed "
                        "through this endpoint."
                    )
                })

            if (
                actor_membership.role == WorkspaceMembership.Role.ADMIN
                and target_membership.role != WorkspaceMembership.Role.MEMBER
            ):
                raise PermissionDenied(
                    "Admins can remove members only, not other admins."
                )

            target_membership.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Workspaces - Members"],
    summary="Transfer workspace ownership",
    description=(
        "Transfers workspace ownership to another member. "
        "The current owner becomes an admin and the selected member "
        "becomes the new owner."
    ),
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the workspace.",
        ),
    ],
    request=WorkspaceOwnershipTransferSerializer,
    responses={
        200: WorkspaceMembershipSerializer,
        400: OpenApiResponse(
            description="Invalid membership or ownership transfer request.",
        ),
        403: OpenApiResponse(
            description="Only the workspace owner can transfer ownership.",
        ),
        404: OpenApiResponse(
            description="Workspace or target membership not found.",
        ),
    },
)
class WorkspaceOwnershipTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        with transaction.atomic():
            actor_membership = get_membership_or_404(
                slug=slug,
                user=request.user,
                roles={WorkspaceMembership.Role.OWNER},
                for_update=True,
                permission_message=(
                    "Only the workspace owner can transfer ownership."
                ),
            )
            workspace = actor_membership.workspace

            # Validate only after confirming that the requester is the owner.
            serializer = WorkspaceOwnershipTransferSerializer(
                data=request.data,
            )
            serializer.is_valid(raise_exception=True)
            membership_id = serializer.validated_data["membership_id"]

            target_membership = get_object_or_404(
                WorkspaceMembership.objects.select_for_update(),
                workspace=workspace,
                id=membership_id,
            )

            if target_membership.id == actor_membership.id:
                raise ValidationError({
                    "membership_id": (
                        "You cannot transfer ownership to yourself."
                    )
                })

            actor_membership.role = WorkspaceMembership.Role.ADMIN
            actor_membership.save(update_fields=["role"])

            target_membership.role = WorkspaceMembership.Role.OWNER
            target_membership.save(update_fields=["role"])

        return Response(
            WorkspaceMembershipSerializer(
                target_membership,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Workspaces - Members"],
    summary="Leave workspace",
    description=(
        "Removes the authenticated user's membership from the workspace. "
        "Workspace owners cannot leave directly; they must transfer "
        "ownership or delete the workspace."
    ),
    request=None,
    parameters=[
        OpenApiParameter(
            name="slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="The unique slug of the workspace.",
        ),
    ],
    responses={
        204: OpenApiResponse(
            description="Successfully left the workspace.",
        ),
        400: OpenApiResponse(
            description="Workspace owners cannot leave the workspace.",
        ),
        404: OpenApiResponse(
            description="Workspace or membership not found.",
        ),
    },
)
class WorkspaceLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        with transaction.atomic():
            membership = get_membership_or_404(
                slug=slug,
                user=request.user,
                for_update=True,
            )

            if membership.role == WorkspaceMembership.Role.OWNER:
                raise ValidationError({
                    "detail": (
                        "Workspace owners cannot leave the workspace. "
                        "Transfer ownership or delete the workspace instead."
                    )
                })

            membership.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
