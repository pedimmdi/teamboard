from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions

from tasks.access import get_task_project_access_or_404
from tasks.api.v1.pagination import TaskPageNumberPagination
from tasks.models import Task
from workspaces.access import get_membership_or_404
from workspaces.models import WorkspaceMembership

from .serializers import CalendarQuerySerializer, CalendarTaskSerializer


class CalendarTaskListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarTaskSerializer
    pagination_class = TaskPageNumberPagination

    def get_queryset(self):
        tasks = self.get_scoped_tasks()
        query = CalendarQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        tasks = tasks.filter(
            due_date__range=(filters["start"], filters["end"]),
        )
        assignee = filters.get("assignee")
        if assignee == "me":
            tasks = tasks.filter(assignee=self.request.user)
        elif assignee == "unassigned":
            tasks = tasks.filter(assignee__isnull=True)
        elif assignee is not None:
            tasks = tasks.filter(assignee_id=assignee)
        return tasks.select_related("project", "assignee").order_by("due_date", "pk")


class CalendarProjectTaskListView(CalendarTaskListView):
    @extend_schema(
        tags=["Calendar"],
        summary="List task due dates in a project",
        parameters=[CalendarQuerySerializer],
        operation_id="calendar_project_tasks",
        responses={200: CalendarTaskSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_scoped_tasks(self):
        access = get_task_project_access_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=self.request.user,
        )
        return Task.objects.filter(project_id=access.project_id)


class CalendarWorkspaceTaskListView(CalendarTaskListView):
    @extend_schema(
        tags=["Calendar"],
        summary="List task due dates in a workspace",
        parameters=[CalendarQuerySerializer],
        operation_id="calendar_workspace_tasks",
        responses={200: CalendarTaskSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_scoped_tasks(self):
        membership = get_membership_or_404(self.kwargs["slug"], self.request.user)
        tasks = Task.objects.filter(project__workspace_id=membership.workspace_id)
        if membership.role == WorkspaceMembership.Role.MEMBER:
            tasks = tasks.filter(project__memberships__user_id=self.request.user.pk)
        return tasks
