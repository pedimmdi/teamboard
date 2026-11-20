
from rest_framework import serializers

from tasks.models import Task


class ProjectReportSummarySerializer(serializers.Serializer):
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    active_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    unassigned_tasks = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class TaskStatusDistributionSerializer(serializers.Serializer):
    todo = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    in_review = serializers.IntegerField()
    done = serializers.IntegerField()


class TaskPriorityDistributionSerializer(serializers.Serializer):
    low = serializers.IntegerField()
    medium = serializers.IntegerField()
    high = serializers.IntegerField()
    urgent = serializers.IntegerField()


class MemberWorkloadSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=["manager", "member"],
    )
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()


class ProjectReportSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    as_of = serializers.DateField()
    summary = ProjectReportSummarySerializer()
    status_distribution = TaskStatusDistributionSerializer()
    priority_distribution = TaskPriorityDistributionSerializer()
    member_workload = MemberWorkloadSerializer(many=True)


class WorkspaceProjectSummarySerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class WorkspaceReportSerializer(serializers.Serializer):
    workspace_id = serializers.UUIDField()
    workspace_name = serializers.CharField()
    as_of = serializers.DateField()
    total_projects = serializers.IntegerField()
    summary = ProjectReportSummarySerializer()
    status_distribution = TaskStatusDistributionSerializer()
    priority_distribution = TaskPriorityDistributionSerializer()
    projects = WorkspaceProjectSummarySerializer(many=True)


class AdvancedReportFilters(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    assignee = serializers.RegexField(r"^(?:me|[1-9][0-9]{0,18})\Z", required=False)
    status = serializers.ChoiceField(choices=Task.Status.values, required=False)
    priority = serializers.ChoiceField(choices=Task.Priority.values, required=False)

    def validate(self, attrs):
        start, end = attrs.get("start_date"), attrs.get("end_date")
        if (start is None) != (end is None):
            raise serializers.ValidationError("Provide both start_date and end_date.")
        if start and (end < start or (end - start).days >= 366 or start.year < 3 or end.year >= 9999):
            raise serializers.ValidationError("Use an ordered range of at most 366 days.")
        assignee = attrs.get("assignee")
        if assignee and assignee.isdigit() and int(assignee) > 2**63 - 1:
            raise serializers.ValidationError({"assignee": "Invalid user ID."})
        return attrs


class HistoryFilters(AdvancedReportFilters):
    period = serializers.ChoiceField(choices=["7d", "30d", "90d"], required=False)
    granularity = serializers.ChoiceField(choices=["day", "week"], default="day")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "period" in attrs and "start_date" in attrs:
            raise serializers.ValidationError("Use a preset period or custom dates.")
        return attrs


class RankingFilters(AdvancedReportFilters):
    ordering = serializers.ChoiceField(
        choices=["name", "-name", "total_tasks", "-total_tasks", "completed_tasks",
                 "-completed_tasks", "overdue_tasks", "-overdue_tasks"],
        default="-completed_tasks",
    )


class HistoryBucketSerializer(serializers.Serializer):
    date = serializers.DateField(help_text="UTC day or Monday of the calendar week.")
    start_date = serializers.DateField(help_text="First included day, inclusive.")
    end_date = serializers.DateField(help_text="Last included day, inclusive.")
    created = serializers.IntegerField()
    completed = serializers.IntegerField()


class ReportHistorySerializer(serializers.Serializer):
    completion_tracking_since = serializers.DateTimeField(allow_null=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    results = HistoryBucketSerializer(many=True)
    previous_results = HistoryBucketSerializer(many=True)


class ReportWorkloadSerializer(serializers.Serializer):
    assignee = serializers.IntegerField(allow_null=True)
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    active_tasks = serializers.IntegerField()
    overdue_tasks = serializers.IntegerField()
    due_soon_tasks = serializers.IntegerField()
    completion_rate = serializers.FloatField()
