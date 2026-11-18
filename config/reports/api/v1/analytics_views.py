import csv

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from projects.access import (
    get_accessible_workspace_project_ids, get_workspace_project_membership_or_404,
)
from projects.models import Project
from tasks.models import Task

from reports.analytics import filter_current_tasks, history_report, workload_rows
from .serializers import (
    AdvancedReportFilters,
    HistoryFilters,
    RankingFilters,
    ReportHistorySerializer,
    ReportWorkloadSerializer,
    WorkspaceProjectSummarySerializer,
)


class ReportPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class ScopedReportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    filter_serializer = AdvancedReportFilters

    def projects(self, request, slug, project_id=None):
        if project_id is not None:
            access = get_workspace_project_membership_or_404(
                workspace_slug=slug, project_id=project_id, user=request.user,
            )
            return Project.objects.filter(pk=access.project_id)
        return Project.objects.filter(pk__in=get_accessible_workspace_project_ids(
            workspace_slug=slug, user=request.user,
        ))

    def filters(self, request):
        serializer = self.filter_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def current_tasks(self, request, projects, filters):
        return filter_current_tasks(Task.objects.filter(project__in=projects), filters, request.user)


class ReportHistoryView(ScopedReportView):
    serializer_class = ReportHistorySerializer
    filter_serializer = HistoryFilters

    @extend_schema(tags=["Reports"], parameters=[HistoryFilters])
    def get(self, request, **kwargs):
        projects = self.projects(request, **kwargs)
        report = history_report(projects, self.filters(request), request.user, timezone.localdate())
        return Response(self.get_serializer(report).data)


class ReportWorkloadView(ScopedReportView):
    serializer_class = ReportWorkloadSerializer

    @extend_schema(tags=["Reports"], parameters=[AdvancedReportFilters], responses=ReportWorkloadSerializer(many=True))
    def get(self, request, **kwargs):
        projects = self.projects(request, **kwargs)
        tasks = self.current_tasks(request, projects, self.filters(request))
        return Response(self.get_serializer(workload_rows(tasks, timezone.localdate()), many=True).data)


class ReportProjectRankingView(ScopedReportView):
    serializer_class = WorkspaceProjectSummarySerializer
    filter_serializer = RankingFilters
    pagination_class = ReportPagination

    @extend_schema(tags=["Reports"], parameters=[RankingFilters], responses=WorkspaceProjectSummarySerializer(many=True))
    def get(self, request, **kwargs):
        projects = self.projects(request, **kwargs)
        filters = self.filters(request)
        tasks = self.current_tasks(request, projects, filters)
        included = Q(tasks__in=tasks)
        done = Q(tasks__status=Task.Status.DONE)
        rows = projects.annotate(
            total_tasks=Count("tasks", filter=included),
            completed_tasks=Count("tasks", filter=included & done),
            overdue_tasks=Count("tasks", filter=included & ~done & Q(tasks__due_date__lt=timezone.localdate())),
        ).order_by(filters["ordering"], "pk").values("id", "name", "total_tasks", "completed_tasks", "overdue_tasks")
        page = self.paginate_queryset(rows)
        data = [{
            **row, "project_id": row["id"], "project_name": row["name"],
            "completion_rate": round(row["completed_tasks"] * 100 / row["total_tasks"], 2) if row["total_tasks"] else 0,
        } for row in page]
        return self.get_paginated_response(self.get_serializer(data, many=True).data)


CSV_ROW_LIMIT = 5000


def safe_csv_text(value):
    prefix = value[:len(value) - len(value.lstrip())]
    stripped = value.lstrip("".join(chr(code) for code in range(33)) + "\ufeff")
    if stripped.startswith(("=", "+", "-", "@")) or any(ord(char) < 32 for char in prefix) or value.startswith(tuple(chr(code) for code in range(32))):
        return "'" + value
    return value


class ReportExportView(ScopedReportView):
    @extend_schema(tags=["Reports"], parameters=[AdvancedReportFilters], responses={(200, "text/csv"): OpenApiTypes.BINARY})
    def get(self, request, **kwargs):
        projects = self.projects(request, **kwargs)
        tasks = self.current_tasks(request, projects, self.filters(request))
        fields = ("id", "project__name", "title", "status", "priority", "assignee_id", "due_date", "completed_at")
        rows = list(tasks.order_by("pk").values_list(*fields)[:CSV_ROW_LIMIT + 1])
        if len(rows) > CSV_ROW_LIMIT:
            raise ValidationError({"export": "Narrow your filters to export at most 5000 tasks."})
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="task-report.csv"'
        writer = csv.writer(response)
        writer.writerow(("task_id", "project", "title", "status", "priority", "assignee_id", "due_date", "completed_at"))
        writer.writerows(
            [safe_csv_text(value) if isinstance(value, str) else value for value in row]
            for row in rows
        )
        return response
