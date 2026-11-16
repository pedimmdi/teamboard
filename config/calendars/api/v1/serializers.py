from datetime import timedelta
from rest_framework import serializers

from calendars.models import CalendarEvent


class CalendarEventSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "project",
            "title",
            "description",
            "event_type",
            "starts_at",
            "ends_at",
            "all_day",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return super().to_internal_value(data)

        allowed_fields = set(self.fields)
        unknown_fields = set(data) - allowed_fields

        if unknown_fields:
            raise serializers.ValidationError({
                field: ["Unknown field."]
                for field in sorted(unknown_fields)
            })

        return super().to_internal_value(data)


class CalendarEventCreateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    title = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        max_length=10000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    event_type = serializers.ChoiceField(
        choices=CalendarEvent.EventType.choices,
        required=False,
        default=CalendarEvent.EventType.EVENT,
    )
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    all_day = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({
                "ends_at": "End time must be after start time."
            })
        return attrs


class CalendarEventUpdateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    title = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        max_length=10000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    event_type = serializers.ChoiceField(
        choices=CalendarEvent.EventType.choices,
        required=False,
    )
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    all_day = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )
        return attrs


class CalendarEventFilterSerializer(serializers.Serializer):
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)

    event_type = serializers.ChoiceField(
        choices=CalendarEvent.EventType.choices,
        required=False,
    )

    def validate(self, attrs):
        start = attrs.get("start")
        end = attrs.get("end")

        if (start is None) != (end is None):
            raise serializers.ValidationError({
                "date_range": (
                    "Provide both start and end, "
                    "or omit both."
                )
            })

        if start is not None:
            if end <= start:
                raise serializers.ValidationError({
                    "end": "End must be after start."
                })

            if end - start > timedelta(days=93):
                raise serializers.ValidationError({
                    "date_range": (
                        "Date range cannot exceed 93 days."
                    )
                })

        return attrs


class CalendarTimelineFilterSerializer(
    CalendarEventFilterSerializer
):
    start = serializers.DateTimeField(required=True)
    end = serializers.DateTimeField(required=True)

    # Timeline combines events and tasks, so event_type
    # filtering is not supported here.
    event_type = None


class CalendarTimelineItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    item_type = serializers.ChoiceField(
        choices=["event", "task"],
    )
    project = serializers.UUIDField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    all_day = serializers.BooleanField()
    event_type = serializers.CharField(allow_null=True)
    task_status = serializers.CharField(allow_null=True)
    task_priority = serializers.CharField(allow_null=True)


class CalendarTimelineResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = CalendarTimelineItemSerializer(many=True)
