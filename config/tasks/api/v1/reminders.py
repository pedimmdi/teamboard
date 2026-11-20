from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from collections.abc import Mapping
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema
from tasks.models import TaskReminder, Task
from tasks.access import get_task_or_404
from tasks.services import _lock_project
from tasks.reminders import save_reminder, cancel_reminder, sync_task_reminders

class AwareDateTime(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value, str) else value
            if not parsed or parsed.tzinfo is None:
                self.fail("invalid", format="ISO 8601 with Z or an explicit UTC offset")
        except (ValueError, TypeError, AttributeError):
            self.fail("invalid", format="ISO 8601 with Z or an explicit UTC offset")
        return super().to_internal_value(value)

class ReminderWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TaskReminder.Kind.choices)
    timezone = serializers.CharField(max_length=64, default="UTC")
    run_at = AwareDateTime(required=False)
    days_before = serializers.IntegerField(min_value=0, max_value=365, required=False)
    local_time = serializers.TimeField(required=False)
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "This field cannot be supplied." for key in unknown})
        return super().to_internal_value(data)
    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Choose a valid IANA timezone.")
        return value
    def validate_local_time(self, value):
        if value.tzinfo is not None:
            raise serializers.ValidationError("Use a local clock time without an offset.")
        return value
    def validate(self, attrs):
        current = self.context.get("reminder")
        kind = attrs.get("kind", current.kind if current else None)
        switching = current is None or kind != current.kind
        if kind == "absolute":
            if switching and "run_at" not in attrs:
                raise serializers.ValidationError({"run_at": "An absolute reminder requires a time."})
            if "days_before" in attrs or "local_time" in attrs:
                raise serializers.ValidationError("Absolute reminders do not accept relative fields.")
        if kind == "relative":
            if "run_at" in attrs:
                raise serializers.ValidationError({"run_at": "Relative times are calculated from the task due date."})
            if switching:
                from datetime import time
                attrs.setdefault("days_before", 0)
                attrs.setdefault("local_time", time(9))
        if not attrs:
            raise serializers.ValidationError("Provide a reminder change.")
        return attrs

class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskReminder
        fields = ("id", "kind", "timezone", "run_at", "days_before", "local_time", "status", "sent_at", "last_error", "attempts", "created_at", "updated_at")
        read_only_fields = fields

class ReminderPagination(PageNumberPagination):
    page_size = 20

class ReminderBase(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReminderSerializer
    throttle_classes = [ScopedRateThrottle]
    pagination_class = ReminderPagination
    def get_throttles(self):
        self.throttle_scope = "reminder_read" if self.request.method == "GET" else "reminder_write"
        return super().get_throttles()
    def task(self):
        return get_task_or_404(workspace_slug=self.kwargs["slug"], project_id=self.kwargs["project_id"], task_id=self.kwargs["task_id"], user=self.request.user)

class TaskReminderListView(ReminderBase):
    @extend_schema(tags=["Tasks"], summary="List only your own task reminders", responses=ReminderSerializer(many=True))
    def get(self, request, *args, **kwargs):
        with transaction.atomic():
            task = self.task()
            _lock_project(project_id=task.project_id)
            task = self.task()
            task = Task.objects.select_for_update().get(pk=task.pk)
            sync_task_reminders(task)
            rows = TaskReminder.objects.filter(task=task, recipient=request.user).order_by(Case(When(status__in=("pending","disabled","invalid","failed"), then=Value(0)), default=Value(1), output_field=IntegerField()), "-created_at", "id")
            return self.get_paginated_response(ReminderSerializer(self.paginate_queryset(rows), many=True).data)
    @extend_schema(tags=["Tasks"], summary="Create a private reminder for yourself (maximum three active)", request=ReminderWriteSerializer, responses={201: ReminderSerializer})
    def post(self, request, *args, **kwargs):
        task = self.task()
        serializer = ReminderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reminder = save_reminder(task=task, actor=request.user, data=serializer.validated_data)
        return Response(ReminderSerializer(reminder).data, status=status.HTTP_201_CREATED)

class TaskReminderDetailView(ReminderBase):
    @extend_schema(tags=["Tasks"], summary="Reschedule your own unsent reminder", request=ReminderWriteSerializer, responses=ReminderSerializer)
    def patch(self, request, *args, **kwargs):
        task = self.task()
        reminder = get_object_or_404(TaskReminder, pk=kwargs["reminder_id"], task=task, recipient=request.user)
        serializer = ReminderWriteSerializer(data=request.data, partial=True, context={"reminder": reminder})
        serializer.is_valid(raise_exception=True)
        reminder = save_reminder(task=task, actor=request.user, data=serializer.validated_data, reminder_id=reminder.pk)
        return Response(ReminderSerializer(reminder).data)
    @extend_schema(tags=["Tasks"], summary="Cancel your own reminder", responses={204: None})
    def delete(self, request, *args, **kwargs):
        cancel_reminder(task=self.task(), actor=request.user, reminder_id=kwargs["reminder_id"])
        return Response(status=status.HTTP_204_NO_CONTENT)
