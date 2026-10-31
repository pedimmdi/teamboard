
from django.urls import path

from .views import (
    ProjectListCreateView,
    ProjectDetailView,
    ProjectMemberListCreateView,
    ProjectMemberRoleUpdateView,
    ProjectMemberRemoveView,
    ProjectLeaveView,
)

app_name = "projects_api_v1"

urlpatterns = [
    path(
        "",
        ProjectListCreateView.as_view(),
        name="project-list-create",
    ),
    path(
        "<uuid:project_id>/",
        ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "<uuid:project_id>/leave/",
        ProjectLeaveView.as_view(),
        name="project-leave",
    ),
    path(
        "<uuid:project_id>/members/",
        ProjectMemberListCreateView.as_view(),
        name="project-member-list-create",
    ),
    path(
        "<uuid:project_id>/members/<uuid:membership_id>/role/",
        ProjectMemberRoleUpdateView.as_view(),
        name="project-member-role-update",
    ),
    path(
        "<uuid:project_id>/members/<uuid:membership_id>/",
        ProjectMemberRemoveView.as_view(),
        name="project-member-remove",
    ),
]
