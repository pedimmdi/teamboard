
from django.urls import path

from .views import ProjectReportView


app_name = "reports_project_api_v1"

urlpatterns = [
    path(
        "",
        ProjectReportView.as_view(),
        name="project-report",
    ),
]
