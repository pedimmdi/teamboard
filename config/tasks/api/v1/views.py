from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from projects.models import Project
from tasks.access import (
    get_task_project_access_or_404,
    get_accessible_project_tasks,
    get_task_or_404,
)
from tasks.services import (
    create_task,
    update_task,
    delete_task,
)

from .serializers import (
    TaskSerializer,
    TaskCreateSerializer,
    TaskUpdateSerializer,
)
from .pagination import TaskPageNumberPagination


@extend_schema_view(
    get=extend_schema(
        tags=["Tasks"],
        summary="List project tasks",
        operation_id="tasks_list",
        responses={200: TaskSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Tasks"],
        summary="Create project task",
        operation_id="tasks_create",
        request=TaskCreateSerializer,
        responses={201: TaskSerializer},
    ),
)
class TaskListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskSerializer
    pagination_class = TaskPageNumberPagination

    def get_project(self):
        get_task_project_access_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=self.request.user,
        )

        return get_object_or_404(
            Project,
            pk=self.kwargs["project_id"],
            workspace__slug=self.kwargs["slug"],
        )

    def get(self, request, *args, **kwargs):
        queryset = get_accessible_project_tasks(
            workspace_slug=kwargs["slug"],
            project_id=kwargs["project_id"],
            user=request.user,
        ).order_by("-created_at", "-pk")

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = TaskSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(
                serializer.data
            )

        serializer = TaskSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        project = self.get_project()

        serializer = TaskCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        task = create_task(
            project=project,
            actor=request.user,
            **serializer.validated_data,
        )

        output = TaskSerializer(
            task,
            context={"request": request},
        )

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Tasks"],
        summary="Retrieve task details",
        operation_id="tasks_retrieve",
        responses={200: TaskSerializer},
    ),
    patch=extend_schema(
        tags=["Tasks"],
        summary="Update task",
        operation_id="tasks_update",
        request=TaskUpdateSerializer,
        responses={200: TaskSerializer},
    ),
    delete=extend_schema(
        tags=["Tasks"],
        summary="Delete task",
        operation_id="tasks_delete",
        responses={204: None},
    ),
)
class TaskDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskSerializer
    http_method_names = [
        "get",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_task(self):
        return get_task_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            task_id=self.kwargs["task_id"],
            user=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        task = self.get_task()

        serializer = TaskSerializer(
            task,
            context={"request": request},
        )

        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        task = self.get_task()

        serializer = TaskUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        changes = serializer.validated_data

        task = update_task(
            task=task,
            actor=request.user,
            title=changes.get("title"),
            description=changes.get("description"),
            status=changes.get("status"),
            priority=changes.get("priority"),
            due_date=changes.get("due_date"),
            update_due_date="due_date" in changes,
            assignee=changes.get("assignee"),
            update_assignee="assignee" in changes,
        )

        output = TaskSerializer(
            task,
            context={"request": request},
        )

        return Response(output.data)

    def delete(self, request, *args, **kwargs):
        task = self.get_task()

        delete_task(
            task=task,
            actor=request.user,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
