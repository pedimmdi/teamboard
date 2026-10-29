from django.urls import path

from .views import (
    WorkspaceDetailView,
    WorkspaceListCreateView,
    WorkspaceInvitationListCreateView,
    WorkspaceInvitationRevokeView,
    WorkspaceInvitationAcceptView,
    WorkspaceMemberListView,
    WorkspaceMemberRoleUpdateView,
    WorkspaceOwnershipTransferView,
    WorkspaceMemberRemoveView,
    WorkspaceLeaveView,
    WorkspaceInvitationResendView,
)

app_name = "workspaces_api_v1"

urlpatterns = [
    path(
        "",
        WorkspaceListCreateView.as_view(),
        name="workspace_list_create",
    ),
    path(
        "<slug:slug>/",
        WorkspaceDetailView.as_view(),
        name="workspace_detail",
    ),
    path(
        "<slug:slug>/invitations/",
        WorkspaceInvitationListCreateView.as_view(),
        name="workspace-invitation-list-create",
    ),
    path(
        "<slug:slug>/invitations/<uuid:invitation_id>/",
        WorkspaceInvitationRevokeView.as_view(),
        name="workspace-invitation-revoke",
    ),
    path(
        "invitations/accept/",
        WorkspaceInvitationAcceptView.as_view(),
        name="workspace-invitation-accept",
    ),
    path(
        "<slug:slug>/members/",
        WorkspaceMemberListView.as_view(),
        name="workspace-member-list",
    ),
    path(
        "<slug:slug>/members/<uuid:membership_id>/role/",
        WorkspaceMemberRoleUpdateView.as_view(),
        name="workspace-member-role-update",
    ),
    path(
        "<slug:slug>/transfer-ownership/",
        WorkspaceOwnershipTransferView.as_view(),
        name="workspace-transfer-ownership",
    ),
    path(
        "<slug:slug>/members/<uuid:membership_id>/",
        WorkspaceMemberRemoveView.as_view(),
        name="workspace-member-remove",
    ),
    path(
        "<slug:slug>/leave/",
        WorkspaceLeaveView.as_view(),
        name="workspace-leave",
    ),
    path(
        "<slug:slug>/invitations/<uuid:invitation_id>/resend/",
        WorkspaceInvitationResendView.as_view(),
        name="workspace-invitation-resend",
    ),
]
