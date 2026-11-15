from django.utils import timezone
from rest_framework import generics, permissions, status, serializers
from rest_framework.generics import get_object_or_404
from drf_spectacular.utils import inline_serializer
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
)

from notifications.models import Notification
from notifications.access import get_accessible_notifications

from .pagination import NotificationPageNumberPagination
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPageNumberPagination

    def get_queryset(self):
        queryset = get_accessible_notifications(
            self.request.user,
        )

        queryset = queryset.select_related("workspace", "project", "task")

        read_filter = self.request.query_params.get("read")

        if read_filter is not None:
            if read_filter not in ("true", "false"):
                raise ValidationError({
                    "read": "Must be true or false.",
                })

            queryset = queryset.filter(
                read_at__isnull=(read_filter == "false"),
            )

        return queryset

    @extend_schema(
        tags=["Notifications"],
        summary="List my notifications",
        operation_id="notifications_list",
        parameters=[
            OpenApiParameter(
                name="read",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter notifications by read status. "
                    "true = read, false = unread."
                ),
            ),
        ],
        responses={200: NotificationSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class NotificationUnreadCountView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Count my unread notifications",
        operation_id="notifications_unread_count",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "unread_count": {
                        "type": "integer",
                    },
                },
                "required": ["unread_count"],
            },
        },
    )
    def get(self, request, *args, **kwargs):
        count = get_accessible_notifications(
            request.user,
        ).filter(
            read_at__isnull=True,
        ).count()

        return Response({
            "unread_count": count,
        })


class NotificationMarkReadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    @extend_schema(
        tags=["Notifications"],
        summary="Mark one notification as read",
        operation_id="notifications_mark_read",
        request=None,
        responses={
            200: NotificationSerializer,
        },
    )
    def post(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(
            get_accessible_notifications(request.user),
            pk=pk,
        )

        if notification.read_at is None:
            now = timezone.now()

            Notification.objects.filter(
                pk=notification.pk,
                read_at__isnull=True,
            ).update(read_at=now)

            notification.refresh_from_db()

        serializer = self.get_serializer(notification)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class NotificationMarkAllReadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="Mark all accessible notifications as read",
        operation_id="notifications_mark_all_read",
        request=None,
        responses={
            200: inline_serializer(
                name="NotificationMarkAllReadResponse",
                fields={
                    "updated_count": serializers.IntegerField(
                        read_only=True,
                        min_value=0,
                    ),
                },
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        accessible_ids = (
            get_accessible_notifications(request.user)
            .filter(read_at__isnull=True)
            .order_by()
            .values("pk")
        )

        updated_count = (
            Notification.objects.filter(
                pk__in=accessible_ids,
                recipient=request.user,
                read_at__isnull=True,
            )
            .update(read_at=timezone.now())
        )

        return Response(
            {"updated_count": updated_count},
            status=status.HTTP_200_OK,
        )
