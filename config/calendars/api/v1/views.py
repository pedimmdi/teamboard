from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiTypes,
)

from calendars.access import (
    get_calendar_project_access_or_404,
    get_calendar_event_or_404,
    get_accessible_project_events,
    get_accessible_workspace_events,
)
from calendars.services import (
    create_calendar_event,
    update_calendar_event,
    delete_calendar_event,
)
from projects.models import Project
from calendars.timeline import get_timeline_items
from .serializers import (
    CalendarEventSerializer,
    CalendarEventCreateSerializer,
    CalendarEventUpdateSerializer,
    CalendarEventFilterSerializer,
    CalendarTimelineFilterSerializer,
    CalendarTimelineResponseSerializer,
)
from .pagination import CalendarEventPagination


CALENDAR_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="start",
        type=OpenApiTypes.DATETIME,
        location=OpenApiParameter.QUERY,
        description="Inclusive range start (ISO 8601).",
    ),
    OpenApiParameter(
        name="end",
        type=OpenApiTypes.DATETIME,
        location=OpenApiParameter.QUERY,
        description="Exclusive range end (ISO 8601).",
    ),
    OpenApiParameter(
        name="event_type",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        enum=["event", "meeting", "deadline"],
    ),
]


def filter_calendar_events(queryset, query_params):
    allowed = {"start", "end", "event_type", "page", "page_size"}
    unexpected = set(query_params.keys()) - allowed

    if unexpected:
        raise ValidationError({
            "query": "Unsupported calendar filter."
        })

    for key in allowed:
        if len(query_params.getlist(key)) > 1:
            raise ValidationError({
                key: "Provide this parameter only once."
            })

    filter_data = {
        key: query_params[key]
        for key in ("start", "end", "event_type")
        if key in query_params
    }

    serializer = CalendarEventFilterSerializer(
        data=filter_data,
    )

    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    if "start" in filters:
        queryset = queryset.filter(
            ends_at__gt=filters["start"],
        )

    if "end" in filters:
        queryset = queryset.filter(
            starts_at__lt=filters["end"],
        )

    if "event_type" in filters:
        queryset = queryset.filter(
            event_type=filters["event_type"],
        )

    return queryset.order_by("starts_at", "id")


@extend_schema_view(
    get=extend_schema(
        tags=["Calendars"],
        summary="List project calendar events",
        operation_id="calendar_project_events_list",
        parameters=CALENDAR_FILTER_PARAMETERS,
        responses={200: CalendarEventSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Calendars"],
        summary="Create project calendar event",
        operation_id="calendar_project_events_create",
        request=CalendarEventCreateSerializer,
        responses={201: CalendarEventSerializer},
    ),
)
class CalendarEventListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarEventSerializer
    pagination_class = CalendarEventPagination

    def get_project(self):
        get_calendar_project_access_or_404(
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
        queryset = get_accessible_project_events(
            workspace_slug=kwargs["slug"],
            project_id=kwargs["project_id"],
            user=request.user,
        )

        queryset = filter_calendar_events(
            queryset,
            request.query_params,
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = CalendarEventSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(
                serializer.data
            )

        return Response(
            CalendarEventSerializer(
                queryset,
                many=True,
            ).data
        )

    def post(self, request, *args, **kwargs):
        project = self.get_project()

        serializer = CalendarEventCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        event = create_calendar_event(
            project=project,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(
            CalendarEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Calendars"],
        summary="Retrieve calendar event",
        operation_id="calendar_events_retrieve",
        responses={200: CalendarEventSerializer},
    ),
    patch=extend_schema(
        tags=["Calendars"],
        summary="Update calendar event",
        operation_id="calendar_events_update",
        request=CalendarEventUpdateSerializer,
        responses={200: CalendarEventSerializer},
    ),
    delete=extend_schema(
        tags=["Calendars"],
        summary="Delete calendar event",
        operation_id="calendar_events_delete",
        responses={204: None},
    ),
)
class CalendarEventDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarEventSerializer

    def get_event(self):
        return get_calendar_event_or_404(
            workspace_slug=self.kwargs["slug"],
            project_id=self.kwargs["project_id"],
            event_id=self.kwargs["event_id"],
            user=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        event = self.get_event()
        return Response(CalendarEventSerializer(event).data)

    def patch(self, request, *args, **kwargs):
        event = self.get_event()

        serializer = CalendarEventUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        event = update_calendar_event(
            event=event,
            actor=request.user,
            **serializer.validated_data,
        )

        return Response(CalendarEventSerializer(event).data)

    def delete(self, request, *args, **kwargs):
        event = self.get_event()

        delete_calendar_event(
            event=event,
            actor=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=["Calendars"],
        summary="List accessible workspace calendar events",
        operation_id="calendar_workspace_events_list",
        parameters=CALENDAR_FILTER_PARAMETERS,
        responses={200: CalendarEventSerializer(many=True)},
    ),
)
class WorkspaceCalendarView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarEventSerializer
    pagination_class = CalendarEventPagination

    def get(self, request, *args, **kwargs):
        queryset = get_accessible_workspace_events(
            workspace_slug=kwargs["slug"],
            user=request.user,
        )

        queryset = filter_calendar_events(
            queryset,
            request.query_params,
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = CalendarEventSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(
                serializer.data
            )

        return Response(
            CalendarEventSerializer(
                queryset,
                many=True,
            ).data
        )


class BaseCalendarTimelineView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarTimelineResponseSerializer

    def get(self, request, *args, **kwargs):
        allowed = {"start", "end"}

        unknown = set(request.query_params) - allowed
        if unknown:
            raise ValidationError({
                "query": "Unsupported timeline parameter."
            })

        for key in allowed:
            if len(request.query_params.getlist(key)) > 1:
                raise ValidationError({
                    key: "Provide this parameter only once."
                })

        serializer = CalendarTimelineFilterSerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        items = get_timeline_items(
            workspace_slug=kwargs["slug"],
            user=request.user,
            start=serializer.validated_data["start"],
            end=serializer.validated_data["end"],
            project_id=kwargs.get("project_id"),
        )

        output = CalendarTimelineResponseSerializer({
            "count": len(items),
            "results": items,
        })

        return Response(output.data)


TIMELINE_PARAMETERS = [
    OpenApiParameter(
        name="start",
        type=OpenApiTypes.DATETIME,
        location=OpenApiParameter.QUERY,
        required=True,
    ),
    OpenApiParameter(
        name="end",
        type=OpenApiTypes.DATETIME,
        location=OpenApiParameter.QUERY,
        required=True,
    ),
]


@extend_schema_view(
    get=extend_schema(
        tags=["Calendars"],
        summary="Get workspace calendar timeline",
        operation_id="workspace_calendar_timeline_list",
        parameters=TIMELINE_PARAMETERS,
        responses={200: CalendarTimelineResponseSerializer},
    ),
)
class WorkspaceCalendarTimelineView(BaseCalendarTimelineView):
    pass


@extend_schema_view(
    get=extend_schema(
        tags=["Calendars"],
        summary="Get project calendar timeline",
        operation_id="project_calendar_timeline_list",
        parameters=TIMELINE_PARAMETERS,
        responses={200: CalendarTimelineResponseSerializer},
    ),
)
class ProjectCalendarTimelineView(BaseCalendarTimelineView):
    pass
