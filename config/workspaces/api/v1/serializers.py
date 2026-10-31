from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer

from workspaces.models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceInvitation,
    generate_workspace_slug,
)


class WorkspaceSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            "id",
            "name",
            "slug",
            "role",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(
        serializers.ChoiceField(
            choices=WorkspaceMembership.Role.choices,
            allow_null=True,
        )
    )
    def get_role(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None

        memberships = getattr(obj, "current_user_memberships", None)
        if memberships is not None:
            return memberships[0].role if memberships else None

        return (
            WorkspaceMembership.objects
            .filter(workspace=obj, user=request.user)
            .values_list("role", flat=True)
            .first()
        )

    def create(self, validated_data):
        user = self.context["request"].user

        # Retry only when the randomly generated slug collides.
        for _ in range(5):
            slug = generate_workspace_slug()

            try:
                with transaction.atomic():
                    workspace = Workspace.objects.create(
                        slug=slug,
                        **validated_data,
                    )
                    WorkspaceMembership.objects.create(
                        workspace=workspace,
                        user=user,
                        role=WorkspaceMembership.Role.OWNER,
                    )

                return workspace

            except IntegrityError:
                if Workspace.objects.filter(slug=slug).exists():
                    continue

                raise

        raise ValidationError({
            "name": "Could not create an workspace. Please try again."
        })


class WorkspaceInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(
        source="invited_by.email",
        read_only=True,
        allow_null=True,
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceInvitation
        fields = (
            "id",
            "email",
            "status",
            "invited_by_email",
            "created_at",
            "expires_at",
            "accepted_at",
            "revoked_at",
        )
        read_only_fields = fields

    @extend_schema_field(
        serializers.ChoiceField(
            choices=WorkspaceInvitation.Status.choices,
        )
    )
    def get_status(self, obj):
        if (
            obj.status == WorkspaceInvitation.Status.PENDING
            and obj.expires_at <= timezone.now()
        ):
            return WorkspaceInvitation.Status.EXPIRED

        return obj.status


class WorkspaceInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(
        write_only=True,
        trim_whitespace=True,
        max_length=200,
    )


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(
        source="user.profile.avatar",
        read_only=True,
        allow_null=True,
    )
    user_id = serializers.IntegerField(source="user.pk", read_only=True)
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceMembership
        fields = (
            "id",
            "user_id",
            "user_email",
            "avatar",
            "role",
            "is_current_user",
            "joined_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_current_user(self, obj):
        request = self.context.get("request")
        return (
            request is not None
            and request.user.is_authenticated
            and obj.user_id == request.user.pk
        )


class WorkspaceMembershipRoleUpdateSerializer(
    serializers.Serializer
):
    role = serializers.ChoiceField(
        choices=(
            WorkspaceMembership.Role.ADMIN,
            WorkspaceMembership.Role.MEMBER,
        )
    )


class WorkspaceOwnershipTransferSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()


@extend_schema_serializer(many=False)
class PaginatedWorkspaceSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = WorkspaceSerializer(many=True)


@extend_schema_serializer(many=False)
class PaginatedWorkspaceMembershipSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = WorkspaceMembershipSerializer(many=True)


@extend_schema_serializer(many=False)
class PaginatedWorkspaceInvitationSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = WorkspaceInvitationSerializer(many=True)
