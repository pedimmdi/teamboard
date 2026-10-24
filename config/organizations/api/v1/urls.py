from django.urls import path

from .views import (
    OrganizationDetailView,
    OrganizationListCreateView,
    OrganizationInvitationListCreateView,
    OrganizationInvitationRevokeView,
    OrganizationInvitationAcceptView,
    OrganizationMemberListView,
    OrganizationMemberRoleUpdateView,
    OrganizationOwnershipTransferView,
    OrganizationMemberRemoveView,
)

app_name = "organizations_api_v1"

urlpatterns = [
    path(
        "",
        OrganizationListCreateView.as_view(),
        name="organization_list_create",
    ),
    path(
        "<slug:slug>/",
        OrganizationDetailView.as_view(),
        name="organization_detail",
    ),
    path(
        "<slug:slug>/invitations/",
        OrganizationInvitationListCreateView.as_view(),
        name="organization-invitation-list-create",
    ),
    path(
        "<slug:slug>/invitations/<uuid:invitation_id>/",
        OrganizationInvitationRevokeView.as_view(),
        name="organization-invitation-revoke",
    ),
    path(
        "invitations/accept/",
        OrganizationInvitationAcceptView.as_view(),
        name="organization-invitation-accept",
    ),
    path(
        "<slug:slug>/members/",
        OrganizationMemberListView.as_view(),
        name="organization-member-list",
    ),
    path(
        "<slug:slug>/members/<uuid:membership_id>/role/",
        OrganizationMemberRoleUpdateView.as_view(),
        name="organization-member-role-update",
    ),
    path(
        "<slug:slug>/transfer-ownership/",
        OrganizationOwnershipTransferView.as_view(),
        name="organization-transfer-ownership",
    ),    
    path(
        "<slug:slug>/members/<uuid:membership_id>/",
        OrganizationMemberRemoveView.as_view(),
        name="organization-member-remove",
    ),
]
