from django.urls import path

from .views import CalendarProjectTaskListView


app_name = "calendar_events_api_v1"

urlpatterns = [
    path("projects/<uuid:project_id>/", CalendarProjectTaskListView.as_view(), name="project-tasks"),
]
