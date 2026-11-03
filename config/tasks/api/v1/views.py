from django.contrib.auth import get_user_model
from django.db.models import Q, Case, When, Value, IntegerField, F
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status, serializers
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
                description=(
                    "Filter tasks by one or more comma-separated "
                    "statuses. Allowed values: todo, in_progress, "
                    "in_review, done. "
                    "Example: status=todo,done."
                ),
            ),
            OpenApiParameter(
                name="due_before",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter tasks with a due date strictly before "
                    "the specified date (exclusive). "
                    "Format: YYYY-MM-DD. "
                    "Tasks without a due date are excluded. "
                    "Example: due_before=2027-03-20."
                ),
            ),
            OpenApiParameter(
                name="overdue",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter overdue tasks. "
                    "When true, return only tasks with a due date "
                    "strictly before today's date that are not done. "
                    "When false, do not apply the overdue filter. "
                    "Accepted values: true, false (case-insensitive). "
                    "Example: overdue=true."
                ),
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
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter tasks by assignee. "
                    "Accepts a valid user ID or the special value "
                    "'me' to filter tasks assigned to the "
                    "authenticated user. "
                    "The value 'me' is case-sensitive. "
                    "Cannot be combined with unassigned=true."
                ),
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
                    "title, priority, or status. Prefix with '-' "
                    "for descending order. Default: -created_at. "
                    "Priority ordering follows low, medium, high, urgent. "
                    "Status ordering follows todo, in_progress, "
                    "in_review, done. "
                    "Tasks without a due_date always appear last "
                    "when ordering by due_date."
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
        due_before = request.query_params.get("due_before")
        overdue = request.query_params.get("overdue")

        if task_status is not None:
            statuses = [
                value.strip()
                for value in task_status.split(",")
            ]

            if any(
                value not in Task.Status.values
                for value in statuses
            ):
                raise ValidationError({
                    "status": "Invalid task status."
                })

            queryset = queryset.filter(
                status__in=statuses,
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
            if assignee == "me":
                assignee_id = request.user.pk
            else:
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

        if due_before is not None:
            date_field = serializers.DateField()

            try:
                parsed_date = date_field.run_validation(due_before)
            except serializers.ValidationError:
                raise ValidationError({
                    "due_before": (
                        "Enter a valid date in YYYY-MM-DD format."
                    )
                })

            queryset = queryset.filter(
                due_date__lt=parsed_date,
            )

        if overdue is not None:
            overdue_value = overdue.lower()

            if overdue_value not in ("true", "false"):
                raise ValidationError({
                    "overdue": "Must be 'true' or 'false'."
                })

            if overdue_value == "true":
                queryset = queryset.filter(
                    due_date__lt=timezone.localdate(),
                ).exclude(
                    status=Task.Status.DONE,
                )

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

        if ordering_field in ("priority", "status"):
            if ordering_field == "priority":
                rank_field = "priority_rank"
                rank_expression = Case(
                    When(priority=Task.Priority.LOW, then=Value(1)),
                    When(priority=Task.Priority.MEDIUM, then=Value(2)),
                    When(priority=Task.Priority.HIGH, then=Value(3)),
                    When(priority=Task.Priority.URGENT, then=Value(4)),
                    output_field=IntegerField(),
                )
            else:
                rank_field = "status_rank"
                rank_expression = Case(
                    When(status=Task.Status.TODO, then=Value(1)),
                    When(status=Task.Status.IN_PROGRESS, then=Value(2)),
                    When(status=Task.Status.IN_REVIEW, then=Value(3)),
                    When(status=Task.Status.DONE, then=Value(4)),
                    output_field=IntegerField(),
                )

            queryset = queryset.annotate(
                **{rank_field: rank_expression}
            )

            ordering_expression = (
                F(rank_field).desc()
                if descending
                else F(rank_field).asc()
            )

        elif ordering_field == "due_date":
            ordering_expression = (
                F("due_date").desc(nulls_last=True)
                if descending
                else F("due_date").asc(nulls_last=True)
            )

        else:
            ordering_expression = ordering

        # Secondary ordering ensures stable pagination.
        queryset = queryset.order_by(
            ordering_expression,
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
