from rest_framework import serializers

from tasks.models import Task


class CalendarQuerySerializer(serializers.Serializer):
    start = serializers.DateField(help_text="First due date, inclusive (YYYY-MM-DD).")
    end = serializers.DateField(help_text="Last due date, inclusive (YYYY-MM-DD).")
    assignee = serializers.RegexField(
        regex=r"^(?:me|unassigned|[1-9][0-9]{0,18})\Z",
        required=False,
        help_text="Filter by user ID, me, or unassigned.",
    )

    def validate(self, attrs):
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError({"end": "End must be on or after start."})
        if "assignee" in attrs and attrs["assignee"].isdigit():
            assignee = int(attrs["assignee"])
            if assignee > 2**63 - 1:
                raise serializers.ValidationError({"assignee": "Invalid user ID."})
            attrs["assignee"] = assignee
        return attrs


class CalendarTaskSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    assignee_email = serializers.EmailField(
        source="assignee.email", read_only=True, allow_null=True,
    )

    class Meta:
        model = Task
        fields = (
            "id", "project", "project_name", "title", "status", "priority",
            "due_date", "assignee", "assignee_email",
        )
        read_only_fields = fields
