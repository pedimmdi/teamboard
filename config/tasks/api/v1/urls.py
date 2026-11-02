from django.urls import path

from .views import (
    TaskListCreateView,
    TaskDetailView,
)


app_name = "tasks_api_v1"

urlpatterns = [
    path(
        "",
        TaskListCreateView.as_view(),
        name="task-list-create",
    ),
    path(
        "<uuid:task_id>/",
        TaskDetailView.as_view(),
        name="task-detail",
    ),
]