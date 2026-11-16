
from rest_framework import serializers


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
