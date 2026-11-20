from django.urls import path

from .views import (
    TaskListCreateView,
    TaskDetailView,
    TaskMoveView,
)


from .reminders import TaskReminderListView, TaskReminderDetailView

app_name = "tasks_api_v1"

urlpatterns = [
    path("<uuid:task_id>/reminders/", TaskReminderListView.as_view(), name="reminder-list"),
    path("<uuid:task_id>/reminders/<uuid:reminder_id>/", TaskReminderDetailView.as_view(), name="reminder-detail"),
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
    path(
        "<uuid:task_id>/move/",
        TaskMoveView.as_view(),
        name="task-move",
    ),
]
