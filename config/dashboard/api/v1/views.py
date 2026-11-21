from drf_spectacular.utils import extend_schema

from rest_framework import generics, permissions
from rest_framework.response import Response

from workspaces.access import get_membership_or_404

from dashboard.services import get_workspace_dashboard
from .serializers import WorkspaceDashboardSerializer


class WorkspaceDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkspaceDashboardSerializer
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Dashboard"],
        operation_id="dashboard_workspace_overview",
        summary="Get the current user's workspace dashboard",
        description=(
            "Returns active assigned tasks and active tasks "
            "created by the user but assigned to someone else. "
            "Only projects accessible within the requested "
            "workspace are included."
        ),
        responses={200: WorkspaceDashboardSerializer},
    )
    def get(self, request, slug, *args, **kwargs):
        membership = get_membership_or_404(
            slug=slug,
            user=request.user,
        )

        data = get_workspace_dashboard(
            workspace=membership.workspace,
            user=request.user,
        )

        serializer = self.get_serializer(data)
        return Response(serializer.data)