from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view

from projects.models import Project, ProjectMembership
from projects.services import (
    create_project,
    add_project_member,
    change_project_member_role,
    remove_project_member,
    delete_project,
    leave_project,
)
from projects.access import get_workspace_project_membership_or_404
from workspaces.access import get_membership_or_404
from workspaces.models import Workspace

from .pagination import ProjectPageNumberPagination
from .serializers import (
    ProjectSerializer,
    ProjectCreateSerializer,
    ProjectUpdateSerializer,
    PaginatedProjectSerializer,
    ProjectMembershipSerializer,
    ProjectMemberAddSerializer,
    ProjectMemberRoleUpdateSerializer,
    PaginatedProjectMembershipSerializer,
)


@extend_schema_view(
    get=extend_schema(
        tags=["Projects"],
        summary="List accessible projects",
        operation_id="projects_list",
        responses={200: PaginatedProjectSerializer},
    ),
    post=extend_schema(
        tags=["Projects"],
        summary="Create project",
        operation_id="projects_create",
        request=ProjectCreateSerializer,
        responses={201: ProjectSerializer},
    ),
)
class ProjectListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProjectPageNumberPagination
    throttle_scope = "project_create"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_workspace_membership(self):
        return get_membership_or_404(
            slug=self.kwargs["slug"],
            user=self.request.user,
        )

    def get_queryset(self):
        workspace = self.get_workspace_membership().workspace

        return (
            Project.objects.filter(
                workspace=workspace,
                memberships__user=self.request.user,
            )
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=ProjectMembership.objects.filter(
                        user=self.request.user,
                    ),
                    to_attr="current_user_memberships",
                )
            )
            .order_by("-created_at", "-pk")
            .distinct()
        )

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ProjectSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = ProjectSerializer(
            queryset,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        membership = self.get_workspace_membership()

        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                project = create_project(
                    workspace=membership.workspace,
                    created_by=request.user,
                    **serializer.validated_data,
                )
        except IntegrityError as exc:
            if (
                getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
                != "unique_project_name_per_workspace"
            ):
                raise

            raise ValidationError({
                "name": "A project with this name already exists."
            }) from exc

        output = ProjectSerializer(
            project,
            context={"request": request},
        )
        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Projects"],
        summary="Retrieve project details",
        operation_id="projects_retrieve",
        responses={200: ProjectSerializer},
    ),
    patch=extend_schema(
        tags=["Projects"],
        summary="Update project",
        operation_id="projects_update",
        request=ProjectUpdateSerializer,
        responses={200: ProjectSerializer},
    ),
    delete=extend_schema(
        tags=["Projects"],
        summary="Delete project",
        description=(
            "Permanently deletes a project. "
            "The requester must be a project manager and "
            "a workspace owner or admin."
        ),
        operation_id="projects_delete",
        responses={204: None},
    ),
)
class ProjectDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProjectSerializer

    def get_project_membership(self, *, roles=None):
        return get_workspace_project_membership_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=self.request.user,
            roles=roles,
        )

    def get(self, request, *args, **kwargs):
        membership = self.get_project_membership()

        serializer = ProjectSerializer(
            membership.project,
            context={"request": request},
        )
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        serializer = ProjectUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                workspace = get_object_or_404(
                    Workspace.objects.select_for_update(),
                    slug=self.kwargs["slug"],
                )

                membership = self.get_project_membership(
                    roles={ProjectMembership.Role.MANAGER},
                )

                project = get_object_or_404(
                    Project.objects.select_for_update(),
                    pk=membership.project_id,
                    workspace=workspace,
                )

                self.get_project_membership(
                    roles={ProjectMembership.Role.MANAGER},
                )

                changes = serializer.validated_data

                if "name" in changes:
                    name = changes["name"]

                    duplicate_exists = Project.objects.filter(
                        workspace=workspace,
                        name__iexact=name,
                    ).exclude(pk=project.pk).exists()

                    if duplicate_exists:
                        raise ValidationError({
                            "name": (
                                "A project with this name "
                                "already exists."
                            )
                        })

                    project.name = name

                if "description" in changes:
                    project.description = changes["description"]

                project.save()

        except IntegrityError as exc:
            if (
                getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
                != "unique_project_name_per_workspace"
            ):
                raise

            raise ValidationError({
                "name": "A project with this name already exists."
            }) from exc

        return Response(
            ProjectSerializer(
                project,
                context={"request": request},
            ).data
        )

    def delete(self, request, *args, **kwargs):
        membership = self.get_project_membership(
            roles={ProjectMembership.Role.MANAGER},
        )

        delete_project(
            project=membership.project,
            actor=request.user,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=["Projects"],
        summary="List project members",
        responses={200: PaginatedProjectMembershipSerializer},
    ),
    post=extend_schema(
        tags=["Projects"],
        summary="Add project member",
        request=ProjectMemberAddSerializer,
        responses={201: ProjectMembershipSerializer},
    ),
)
class ProjectMemberListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProjectPageNumberPagination
    throttle_scope = "project_member_add"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_project_membership(self, *, roles=None):
        return get_workspace_project_membership_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=self.request.user,
            roles=roles,
        )

    def get(self, request, *args, **kwargs):
        membership = self.get_project_membership()

        queryset = (
            ProjectMembership.objects.filter(
                project=membership.project,
                project__workspace__memberships__user=request.user,
            )
            .select_related("user")
            .order_by("joined_at", "pk")
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ProjectMembershipSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = ProjectMembershipSerializer(
            queryset,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        membership = self.get_project_membership(
            roles={ProjectMembership.Role.MANAGER},
        )

        serializer = ProjectMemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]

        # Avoid exposing users outside the workspace.
        User = get_user_model()
        user = get_object_or_404(
            User,
            pk=user_id,
            workspace_memberships__workspace=membership.project.workspace,
        )

        created_membership = add_project_member(
            project=membership.project,
            actor=request.user,
            user=user,
            role=serializer.validated_data["role"],
        )

        return Response(
            ProjectMembershipSerializer(
                created_membership,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Projects"],
    summary="Change project member role",
    request=ProjectMemberRoleUpdateSerializer,
    responses={200: ProjectMembershipSerializer},
)
class ProjectMemberRoleUpdateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["patch", "options", "head"]
    serializer_class = ProjectMemberRoleUpdateSerializer

    def patch(self, request, *args, **kwargs):
        membership = get_workspace_project_membership_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=request.user,
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_membership = change_project_member_role(
            project=membership.project,
            actor=request.user,
            membership_id=self.kwargs["membership_id"],
            role=serializer.validated_data["role"],
        )

        return Response(
            ProjectMembershipSerializer(
                updated_membership,
                context={"request": request},
            ).data
        )


@extend_schema(
    tags=["Projects"],
    summary="Remove project member",
    responses={204: None},
)
class ProjectMemberRemoveView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["delete", "options", "head"]

    def delete(self, request, *args, **kwargs):
        membership = get_workspace_project_membership_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=request.user,
        )

        remove_project_member(
            project=membership.project,
            actor=request.user,
            membership_id=self.kwargs["membership_id"],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectLeaveView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Projects"],
        summary="Leave project",
        description=(
            "Allows a project member to leave voluntarily. "
            "The last project manager cannot leave."
        ),
        operation_id="projects_leave",
        request=None,
        responses={204: None},
    )
    def post(self, request, *args, **kwargs):
        membership = get_workspace_project_membership_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            user=request.user,
        )

        leave_project(
            project=membership.project,
            actor=request.user,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
