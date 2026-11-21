from django.urls import path

from .views import WorkspaceDashboardView


app_name = "dashboard_api_v1"

urlpatterns = [
    path(
        "",
        WorkspaceDashboardView.as_view(),
        name="overview",
    ),
]