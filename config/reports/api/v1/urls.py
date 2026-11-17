
from django.urls import path

from .analytics_views import ReportHistoryView, ReportWorkloadView, ReportExportView, ReportProjectRankingView
from .views import WorkspaceReportView


app_name = "reports_api_v1"

urlpatterns = [
    path("history/", ReportHistoryView.as_view(), name="history"),
    path("workload/", ReportWorkloadView.as_view(), name="workload"),
    path("export/", ReportExportView.as_view(), name="export"),
    path("projects/", ReportProjectRankingView.as_view(), name="projects"),
    path(
        "",
        WorkspaceReportView.as_view(),
        name="workspace-report",
    ),
]
