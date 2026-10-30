from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from projects.models import Project, ProjectMembership


class ProjectSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "description",
            "role",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(
        serializers.ChoiceField(
            choices=ProjectMembership.Role.choices,
            allow_null=True,
        )
    )
    def get_role(self, obj):
        memberships = getattr(
            obj,
            "current_user_memberships",
            None,
        )

        if memberships is not None:
            return memberships[0].role if memberships else None

        request = self.context.get("request")

        if request is None or not request.user.is_authenticated:
            return None

        return (
            ProjectMembership.objects
            .filter(project=obj, user=request.user)
            .values_list("role", flat=True)
            .first()
        )


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        allow_blank=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )


class PaginatedProjectSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ProjectSerializer(many=True)


class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        allow_blank=False,
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )
        return attrs


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        source="user.pk",
        read_only=True,
    )
    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMembership
        fields = (
            "id",
            "user_id",
            "user_email",
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


class ProjectMemberAddSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(
        choices=ProjectMembership.Role.choices,
        default=ProjectMembership.Role.MEMBER,
    )


class ProjectMemberRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=ProjectMembership.Role.choices,
    )


class PaginatedProjectMembershipSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ProjectMembershipSerializer(many=True)
