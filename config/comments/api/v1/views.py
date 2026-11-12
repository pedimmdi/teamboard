
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

from comments.access import (
    get_comment_task_or_404,
    get_accessible_task_comments,
    get_comment_or_404,
)
from comments.services import (
    create_comment,
    update_comment,
    delete_comment,
)
from comments.models import Comment, CommentAttachment
from comments.storage import attachment_storage

from .pagination import CommentPageNumberPagination
from .serializers import (
    CommentSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
)


@extend_schema_view(
    get=extend_schema(
        tags=["Comments"],
        summary="List task comments",
        operation_id="comments_list",
        responses={200: CommentSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Comments"],
        summary="Create task comment",
        operation_id="comments_create",
        request=CommentCreateSerializer,
        responses={201: CommentSerializer},
    ),
)
class CommentListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer
    pagination_class = CommentPageNumberPagination
    throttle_scope = "comment_create"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_task(self):
        return get_comment_task_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            task_id=self.kwargs["task_id"],
            user=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        queryset = get_accessible_task_comments(
            workspace_slug=kwargs["slug"],
            project_id=kwargs["project_id"],
            task_id=kwargs["task_id"],
            user=request.user,
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        serializer = CommentSerializer(
            page,
            many=True,
            context={"request": request},
        )

        return paginator.get_paginated_response(
            serializer.data
        )

    def post(self, request, *args, **kwargs):
        task = self.get_task()

        serializer = CommentCreateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        comment = create_comment(
            task=task,
            actor=request.user,
            **serializer.validated_data,
        )

        comment = get_object_or_404(
            Comment.objects.select_related(
                "author",
                "author__profile", "attachment",
            ).prefetch_related("mentions"),
            pk=comment.pk,
            task_id=task.pk,
        )

        return Response(
            CommentSerializer(
                comment,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Comments"],
        summary="Retrieve task comment",
        operation_id="comments_retrieve",
        responses={200: CommentSerializer},
    ),
    patch=extend_schema(
        tags=["Comments"],
        summary="Update own comment",
        operation_id="comments_update",
        request=CommentUpdateSerializer,
        responses={200: CommentSerializer},
    ),
    delete=extend_schema(
        tags=["Comments"],
        summary="Delete task comment",
        operation_id="comments_delete",
        responses={204: None},
    ),
)
class CommentDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    def get_comment(self):
        return get_comment_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            task_id=self.kwargs["task_id"],
            comment_id=self.kwargs["comment_id"],
            user=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        comment = self.get_comment()

        return Response(
            CommentSerializer(
                comment,
                context={"request": request},
            ).data
        )

    def patch(self, request, *args, **kwargs):
        comment = self.get_comment()

        serializer = CommentUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        comment = update_comment(
            comment=comment,
            actor=request.user,
            **serializer.validated_data,
        )

        comment.refresh_from_db()

        return Response(
            CommentSerializer(
                comment,
                context={"request": request},
            ).data
        )

    def delete(self, request, *args, **kwargs):
        comment = self.get_comment()

        delete_comment(
            comment=comment,
            actor=request.user,
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class CommentAttachmentView(CommentDetailView):
    http_method_names = ["get", "head", "options"]

    @extend_schema(tags=["Comments"], operation_id="comments_attachment_download", responses=OpenApiTypes.BINARY)
    def get(self, request, *args, **kwargs):
        comment = self.get_comment()
        attachment = get_object_or_404(CommentAttachment, comment=comment)
        try:
            file = attachment_storage().open(attachment.storage_key, 'rb')
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(
            file, as_attachment=True,
            filename=attachment.filename, content_type="application/octet-stream",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
