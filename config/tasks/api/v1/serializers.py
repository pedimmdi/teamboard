from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import serializers

from projects.models import ProjectMembership
from tasks.models import Task


User = get_user_model()


class ProjectAssigneeField(serializers.PrimaryKeyRelatedField):
    default_error_messages = {
        "does_not_exist": "Invalid assignee for this project.",
        "incorrect_type": "Invalid assignee for this project.",
    }

    def __init__(self, **kwargs):
        super().__init__(
            queryset=User.objects.none(),
            **kwargs,
        )

    def get_queryset(self):
        project_id = self.context.get("project_id")

        if project_id is None:
            return User.objects.none()

        eligible_user_ids = ProjectMembership.objects.filter(
            project_id=project_id,
            project__workspace__memberships__user_id=(
                models.F("user_id")
            ),
        ).values("user_id")

        return User.objects.filter(
            pk__in=eligible_user_ids,
        )


class TaskSerializer(serializers.ModelSerializer):
    assignee_email = serializers.EmailField(
        source="assignee.email",
        read_only=True,
        allow_null=True,
    )
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        allow_null=True,
    )
    assignee_avatar = serializers.ImageField(
        source="assignee.profile.avatar",
        read_only=True,
        allow_null=True,
    )
    created_by_avatar = serializers.ImageField(
        source="created_by.profile.avatar",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = (
            "id",
            "project",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "assignee_email",
            "assignee_avatar",
            "created_by",
            "created_by_email",
            "created_by_avatar",
            "due_date",
            "position",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class TaskCreateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
        allow_blank=False,
    )

    description = serializers.CharField(
        max_length=10000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    status = serializers.ChoiceField(
        choices=Task.Status.choices,
        required=False,
        default=Task.Status.TODO,
    )

    priority = serializers.ChoiceField(
        choices=Task.Priority.choices,
        required=False,
        default=Task.Priority.MEDIUM,
    )

    assignee = ProjectAssigneeField(
        required=False,
        allow_null=True,
    )

    due_date = serializers.DateField(
        required=False,
        allow_null=True,
    )


class TaskUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=200,
        required=False,
        trim_whitespace=True,
        allow_blank=False,
    )

    description = serializers.CharField(
        max_length=10000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )

    status = serializers.ChoiceField(
        choices=Task.Status.choices,
        required=False,
    )

    priority = serializers.ChoiceField(
        choices=Task.Priority.choices,
        required=False,
    )

    assignee = ProjectAssigneeField(
        required=False,
        allow_null=True,
    )

    due_date = serializers.DateField(
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        return attrs


class TaskMoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Task.Status.choices,
        required=True,
    )

    position = serializers.IntegerField(
        min_value=0,
        required=False,
        help_text="Zero-based destination index. Send exactly one of position, before_task, or placement.",
    )

    before_task = serializers.UUIDField(
        required=False,
        help_text="Destination task in the requested status column; resolved under the project lock.",
    )
    placement = serializers.ChoiceField(
        choices=("first", "last"),
        required=False,
        help_text="Place at the current start or end of the destination column.",
    )

    def validate(self, attrs):
        if sum(key in attrs for key in ("position", "before_task", "placement")) != 1:
            raise serializers.ValidationError(
                "Provide exactly one of position, before_task, or placement."
            )
        return attrs
