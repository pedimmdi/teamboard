
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from notifications.models import Notification
from workspaces.api.v1.views import (
    WorkspaceMemberRoleUpdateView,
    WorkspaceOwnershipTransferView,
)
from workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from workspaces.services import (
    create_workspace_invitation,
    resend_workspace_invitation,
)


User = get_user_model()


class WorkspaceNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="workspace-notif-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="workspace-notif-member@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Workspace Notification Tests",
        )

        self.owner_membership = WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )

        self.member_membership = WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.factory = APIRequestFactory()

    def patch_role(self, role, actor=None):
        actor = actor or self.owner

        request = self.factory.patch(
            "/workspace/member/role/",
            {"role": role},
            format="json",
        )
        force_authenticate(request, user=actor)

        return WorkspaceMemberRoleUpdateView.as_view()(
            request,
            slug=self.workspace.slug,
            membership_id=self.member_membership.pk,
        )

    def transfer_ownership(self):
        request = self.factory.post(
            "/workspace/transfer/",
            {"membership_id": str(self.member_membership.pk)},
            format="json",
        )
        force_authenticate(request, user=self.owner)

        return WorkspaceOwnershipTransferView.as_view()(
            request,
            slug=self.workspace.slug,
        )

    def test_invitation_notifies_existing_active_user(self):
        self.member_membership.delete()

        invitation = create_workspace_invitation(
            workspace=self.workspace,
            invited_by=self.owner,
            email=self.member.email,
        )

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.WORKSPACE_INVITED,
        )
        self.assertEqual(notification.recipient_id, self.member.pk)
        self.assertEqual(notification.actor_id, self.owner.pk)
        self.assertEqual(notification.workspace_id, self.workspace.pk)
        self.assertIsNone(notification.project_id)
        self.assertIsNone(notification.task_id)
        self.assertEqual(
            notification.payload,
            {"invitation_id": str(invitation.pk)},
        )
        self.assertNotIn("token", str(notification.payload).lower())

    def test_invitation_for_unknown_email_has_no_notification(self):
        create_workspace_invitation(
            workspace=self.workspace,
            invited_by=self.owner,
            email="unknown-notif@example.com",
        )

        self.assertFalse(Notification.objects.exists())

    def test_invitation_for_inactive_user_has_no_notification(self):
        self.member_membership.delete()
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])

        create_workspace_invitation(
            workspace=self.workspace,
            invited_by=self.owner,
            email=self.member.email,
        )

        self.assertFalse(Notification.objects.exists())

    def test_invitation_resend_does_not_duplicate_notification(self):
        self.member_membership.delete()

        invitation = create_workspace_invitation(
            workspace=self.workspace,
            invited_by=self.owner,
            email=self.member.email,
        )

        resend_workspace_invitation(
            workspace=self.workspace,
            invitation_id=invitation.pk,
            invited_by=self.owner,
        )

        self.assertEqual(
            Notification.objects.filter(
                event_type=Notification.EventType.WORKSPACE_INVITED,
            ).count(),
            1,
        )

    def test_role_change_creates_notification(self):
        response = self.patch_role(
            WorkspaceMembership.Role.ADMIN,
        )

        self.assertEqual(response.status_code, 200, response.data)

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )
        self.assertEqual(notification.recipient_id, self.member.pk)
        self.assertEqual(notification.actor_id, self.owner.pk)
        self.assertEqual(notification.workspace_id, self.workspace.pk)
        self.assertIsNone(notification.project_id)
        self.assertIsNone(notification.task_id)
        self.assertEqual(
            notification.payload,
            {
                "old_role": WorkspaceMembership.Role.MEMBER,
                "new_role": WorkspaceMembership.Role.ADMIN,
            },
        )

    def test_same_role_creates_no_notification(self):
        response = self.patch_role(
            WorkspaceMembership.Role.MEMBER,
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Notification.objects.exists())

    def test_multiple_role_changes_create_distinct_notifications(self):
        for role in (
            WorkspaceMembership.Role.ADMIN,
            WorkspaceMembership.Role.MEMBER,
        ):
            response = self.patch_role(role)
            self.assertEqual(response.status_code, 200, response.data)

        notifications = list(
            Notification.objects.filter(
                event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
            )
        )

        self.assertEqual(len(notifications), 2)
        self.assertNotEqual(
            notifications[0].deduplication_key,
            notifications[1].deduplication_key,
        )

    def test_ownership_transfer_notifies_new_owner(self):
        response = self.transfer_ownership()

        self.assertEqual(response.status_code, 200, response.data)

        self.owner_membership.refresh_from_db()
        self.member_membership.refresh_from_db()

        self.assertEqual(
            self.owner_membership.role,
            WorkspaceMembership.Role.ADMIN,
        )
        self.assertEqual(
            self.member_membership.role,
            WorkspaceMembership.Role.OWNER,
        )

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.WORKSPACE_ROLE_CHANGED,
        )
        self.assertEqual(notification.recipient_id, self.member.pk)
        self.assertEqual(
            notification.payload,
            {
                "old_role": WorkspaceMembership.Role.MEMBER,
                "new_role": WorkspaceMembership.Role.OWNER,
            },
        )

    def test_role_notification_failure_rolls_back_change(self):
        with patch(
            "workspaces.api.v1.views.notify_workspace_role_changed",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                self.patch_role(WorkspaceMembership.Role.ADMIN)

        self.member_membership.refresh_from_db()
        self.assertEqual(
            self.member_membership.role,
            WorkspaceMembership.Role.MEMBER,
        )
        self.assertFalse(Notification.objects.exists())

    def test_invitation_notification_failure_rolls_back_invitation(self):
        self.member_membership.delete()

        with patch(
            "workspaces.services.notify_workspace_invited",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                create_workspace_invitation(
                    workspace=self.workspace,
                    invited_by=self.owner,
                    email=self.member.email,
                )

        self.assertFalse(WorkspaceInvitation.objects.exists())
        self.assertFalse(Notification.objects.exists())
