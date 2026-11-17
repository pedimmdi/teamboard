
from django.urls import path

from .analytics_views import ReportHistoryView, ReportWorkloadView, ReportExportView
from .views import ProjectReportView


app_name = "reports_project_api_v1"

urlpatterns = [
    path("history/", ReportHistoryView.as_view(), name="history"),
    path("workload/", ReportWorkloadView.as_view(), name="workload"),
    path("export/", ReportExportView.as_view(), name="export"),
    path(
        "",
        ProjectReportView.as_view(),
        name="project-report",
    ),
]
