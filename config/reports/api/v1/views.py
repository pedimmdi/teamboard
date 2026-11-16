from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response

from projects.access import (
    get_workspace_project_membership_or_404,
)
from workspaces.access import get_membership_or_404
from reports.services import get_project_report, get_workspace_report
from .serializers import ProjectReportSerializer, WorkspaceReportSerializer


class ProjectReportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectReportSerializer
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Reports"],
        summary="Get project analytics",
        description=(
            "Returns current task statistics, status and "
            "priority distributions, and member workload. "
            "Accessible to project members and workspace "
            "owners/admins."
        ),
        operation_id="reports_project_overview",
        responses={200: ProjectReportSerializer},
    )
    def get(self, request, *args, **kwargs):
        membership = (
            get_workspace_project_membership_or_404(
                workspace_slug=kwargs["slug"],
                project_id=kwargs["project_id"],
                user=request.user,
            )
        )

        report = get_project_report(
            project=membership.project,
        )

        serializer = self.get_serializer(report)
        return Response(serializer.data)


class WorkspaceReportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkspaceReportSerializer
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Reports"],
        summary="Get workspace analytics",
        description=(
            "Returns aggregated task analytics for projects "
            "accessible to the authenticated user. "
            "Workspace owners and admins can see all projects."
        ),
        operation_id="reports_workspace_overview",
        responses={200: WorkspaceReportSerializer},
    )
    def get(self, request, *args, **kwargs):
        membership = get_membership_or_404(
            slug=kwargs["slug"],
            user=request.user,
        )

        report = get_workspace_report(
            workspace=membership.workspace,
            user=request.user,
        )

        serializer = self.get_serializer(report)
        return Response(serializer.data)
