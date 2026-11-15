from django.urls import path

from .views import CalendarProjectTaskListView, CalendarWorkspaceTaskListView


app_name = "calendar_events_api_v1"

urlpatterns = [
    path("", CalendarWorkspaceTaskListView.as_view(), name="workspace-tasks"),
    path("projects/<uuid:project_id>/", CalendarProjectTaskListView.as_view(), name="project-tasks"),
]
