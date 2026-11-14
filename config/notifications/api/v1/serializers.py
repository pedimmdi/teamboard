
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from notifications.models import Notification


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
        """
        Do not expose unvalidated event payloads.

        Event-specific public payload schemas will be introduced
        before notification producers are connected.
        """
        return {}
