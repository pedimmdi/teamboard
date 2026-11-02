from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
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
from tasks.models import Task
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
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter tasks by status.",
                enum=Task.Status.values,
            ),
            OpenApiParameter(
                name="priority",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter tasks by priority.",
                enum=Task.Priority.values,
            ),
            OpenApiParameter(
                name="assignee",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by assigned user ID.",
            ),
            OpenApiParameter(
                name="unassigned",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    "Use true to return only unassigned tasks. "
                    "Cannot be combined with assignee."
                ),
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Case-insensitive search in title and "
                    "description. Maximum 200 characters."
                ),
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Order by created_at, updated_at, due_date, "
                    "title, priority, or status. Prefix with "
                    "'-' for descending order. Default: -created_at. "
                    "Priority uses alphabetical ordering."
                ),
            ),
        ],
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
    throttle_scope = "task_create"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]

        return []

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
        )

        task_status = request.query_params.get("status")
        priority = request.query_params.get("priority")
        assignee = request.query_params.get("assignee")
        unassigned = request.query_params.get("unassigned")

        if task_status is not None:
            if task_status not in Task.Status.values:
                raise ValidationError({
                    "status": "Invalid task status."
                })

            queryset = queryset.filter(
                status=task_status,
            )

        if priority is not None:
            if priority not in Task.Priority.values:
                raise ValidationError({
                    "priority": "Invalid task priority."
                })

            queryset = queryset.filter(
                priority=priority,
            )

        if assignee is not None:
            User = get_user_model()
            pk_field = User._meta.pk

            try:
                assignee_id = pk_field.to_python(assignee)
            except (
                DjangoValidationError,
                ValueError,
                TypeError,
            ):
                raise ValidationError({
                    "assignee": "Invalid user ID."
                })

            queryset = queryset.filter(
                assignee_id=assignee_id,
            )

        if unassigned is not None:
            if unassigned not in ("true", "false"):
                raise ValidationError({
                    "unassigned": "Must be true or false."
                })

            if unassigned == "true":
                queryset = queryset.filter(
                    assignee__isnull=True,
                )

        if assignee is not None and unassigned == "true":
            raise ValidationError({
                "unassigned": (
                    "Cannot combine assignee with "
                    "unassigned=true."
                )
            })

        # Searching
        search = request.query_params.get("search")

        if search is not None:
            search = search.strip()

            if search:
                if len(search) > 200:
                    raise ValidationError({
                        "search": (
                            "Search query cannot exceed "
                            "200 characters."
                        )
                    })

                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

        # Ordering
        ordering = request.query_params.get(
            "ordering",
            "-created_at",
        )

        allowed_ordering_fields = {
            "created_at",
            "updated_at",
            "due_date",
            "title",
            "priority",
            "status",
        }

        descending = ordering.startswith("-")
        ordering_field = (
            ordering[1:] if descending else ordering
        )

        if ordering_field not in allowed_ordering_fields:
            raise ValidationError({
                "ordering": "Invalid ordering field."
            })

        # Secondary ordering ensures stable pagination.
        queryset = queryset.order_by(
            ordering,
            "-pk",
        )

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
