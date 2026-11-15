
from uuid import UUID

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from notifications.models import Notification


PUBLIC_PAYLOAD_FIELDS = {
    Notification.EventType.TASK_ASSIGNED: {},
    Notification.EventType.TASK_UPDATED: {
        "changed_fields": "changed_fields",
    },
    Notification.EventType.COMMENT_MENTIONED: {
        "comment_id": "uuid",
    },
    Notification.EventType.COMMENT_REPLIED: {
        "comment_id": "uuid",
        "parent_comment_id": "uuid",
    },
    Notification.EventType.PROJECT_MEMBER_ADDED: {
        "role": "project_role",
    },
    Notification.EventType.PROJECT_ROLE_CHANGED: {
        "old_role": "project_role",
        "new_role": "project_role",
    },
    Notification.EventType.WORKSPACE_INVITED: {
        "invitation_id": "uuid",
    },
    Notification.EventType.WORKSPACE_ROLE_CHANGED: {
        "old_role": "workspace_role",
        "new_role": "workspace_role",
    },
}

TASK_CHANGED_FIELDS = frozenset({
    "title",
    "description",
    "status",
    "priority",
    "due_date",
})

PROJECT_ROLES = frozenset({
    "manager",
    "member",
})

WORKSPACE_ROLES = frozenset({
    "owner",
    "admin",
    "member",
})


def serialize_public_payload(event_type, payload):
    """
    Return only explicitly allowed, validated event data.

    Unknown keys and malformed values are never exposed.
    """

    if not isinstance(payload, dict):
        return {}

    schema = PUBLIC_PAYLOAD_FIELDS.get(event_type)
    if schema is None:
        return {}

    result = {}

    for field, field_type in schema.items():
        value = payload.get(field)

        if field_type == "uuid":
            if not isinstance(value, str):
                continue

            try:
                parsed = UUID(value)
            except (ValueError, AttributeError):
                continue

            result[field] = str(parsed)

        elif field_type == "changed_fields":
            if not isinstance(value, list):
                continue

            if not all(
                isinstance(item, str)
                and item in TASK_CHANGED_FIELDS
                for item in value
            ):
                continue

            result[field] = sorted(set(value))

        elif field_type == "project_role":
            if (
                isinstance(value, str)
                and value in PROJECT_ROLES
            ):
                result[field] = value

        elif field_type == "workspace_role":
            if (
                isinstance(value, str)
                and value in WORKSPACE_ROLES
            ):
                result[field] = value

    return result


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)
    payload = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "actor",
            "workspace",
            "project",
            "task",
            "payload",
            "created_at",
            "read_at",
            "is_read",
        ]
        read_only_fields = fields

    @extend_schema_field(
        serializers.DictField(
            child=serializers.JSONField(),
            read_only=True,
        )
    )
    def get_payload(self, obj) -> dict:
        return serialize_public_payload(
            obj.event_type,
            obj.payload,
        )
