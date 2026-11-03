from django.contrib.auth import get_user_model
from rest_framework import serializers

from tasks.models import Task


User = get_user_model()


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

    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
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

    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
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
        required=True,
    )
