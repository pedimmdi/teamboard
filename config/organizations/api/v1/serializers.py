from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    generate_organization_slug,
)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        user = self.context["request"].user

        # Retry only when the randomly generated slug collides.
        for _ in range(5):
            slug = generate_organization_slug()

            try:
                with transaction.atomic():
                    organization = Organization.objects.create(
                        slug=slug,
                        **validated_data,
                    )
                    OrganizationMembership.objects.create(
                        organization=organization,
                        user=user,
                        role=OrganizationMembership.Role.OWNER,
                    )

                return organization

            except IntegrityError:
                if Organization.objects.filter(slug=slug).exists():
                    continue

                raise

        raise ValidationError({
            "name": "Could not create an organization. Please try again."
        })


class OrganizationInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(
        source="invited_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = OrganizationInvitation
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


class OrganizationInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(
        write_only=True,
        trim_whitespace=True,
        max_length=200,
    )


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    class Meta:
        model = OrganizationMembership
        fields = (
            "id",
            "user_email",
            "role",
            "joined_at",
        )
        read_only_fields = fields


class OrganizationMembershipRoleUpdateSerializer(
    serializers.Serializer
):
    role = serializers.ChoiceField(
        choices=(
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.MEMBER,
        )
    )


class OrganizationOwnershipTransferSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
