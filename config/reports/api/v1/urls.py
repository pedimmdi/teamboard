
from django.urls import path

from .views import WorkspaceReportView


app_name = "reports_api_v1"

urlpatterns = [
    path(
        "",
        WorkspaceReportView.as_view(),
        name="workspace-report",
    ),
]
