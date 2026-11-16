
from django.urls import path

from .views import (
    CalendarEventListCreateView,
    CalendarEventDetailView,
)

app_name = "calendars_api_v1"

urlpatterns = [
    path(
        "",
        CalendarEventListCreateView.as_view(),
        name="calendar-event-list-create",
    ),
    path(
        "<uuid:event_id>/",
        CalendarEventDetailView.as_view(),
        name="calendar-event-detail",
    ),
]
