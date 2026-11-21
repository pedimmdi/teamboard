
from rest_framework import serializers

from calendars.models import CalendarEvent
from notifications.api.v1.serializers import NotificationSerializer
from tasks.models import Task, TaskReminder


class DashboardTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )

    assignee_email = serializers.EmailField(
        source="assignee.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = (
            "id",
            "project",
            "project_name",
            "title",
            "status",
            "priority",
            "assignee",
            "assignee_email",
            "due_date",
            "created_at",
        )
        read_only_fields = fields


class DashboardTaskSectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    items = DashboardTaskSerializer(many=True)


class DashboardProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class DashboardProjectSectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    items = DashboardProjectSerializer(many=True)


class DashboardReminderSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(
        source="task.title",
        read_only=True,
    )

    project = serializers.UUIDField(
        source="task.project_id",
        read_only=True,
    )

    project_name = serializers.CharField(
        source="task.project.name",
        read_only=True,
    )

    class Meta:
        model = TaskReminder
        fields = (
            "id",
            "task",
            "task_title",
            "project",
            "project_name",
            "kind",
            "run_at",
            "timezone",
        )
        read_only_fields = fields


class DashboardReminderSectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    items = DashboardReminderSerializer(many=True)


class DashboardCalendarEventSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "project",
            "project_name",
            "title",
            "event_type",
            "starts_at",
            "ends_at",
            "all_day",
        )
        read_only_fields = fields


class DashboardCalendarSectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    items = DashboardCalendarEventSerializer(many=True)


class DashboardNotificationSectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    unread_count = serializers.IntegerField(min_value=0)
    items = NotificationSerializer(many=True)


class WorkspaceDashboardSerializer(serializers.Serializer):
    today_tasks_count = serializers.IntegerField(min_value=0)
    workspace_id = serializers.UUIDField()
    workspace_name = serializers.CharField()

    as_of = serializers.DateField()
    due_soon_until = serializers.DateField()
    upcoming_until = serializers.DateTimeField()

    my_tasks = DashboardTaskSectionSerializer()
    follow_up = DashboardTaskSectionSerializer()
    overdue_tasks = DashboardTaskSectionSerializer()
    due_soon_tasks = DashboardTaskSectionSerializer()
    completed_tasks = DashboardTaskSectionSerializer()

    projects = DashboardProjectSectionSerializer()

    upcoming_reminders = DashboardReminderSectionSerializer()
    upcoming_events = DashboardCalendarSectionSerializer()
    recent_notifications = DashboardNotificationSectionSerializer()
