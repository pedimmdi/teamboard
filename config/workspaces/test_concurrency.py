from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connections
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from workspaces.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from workspaces.services import create_workspace_invitation
from notifications.models import Notification


User = get_user_model()


class WorkspaceInvitationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="concurrent-owner@example.com",
        )

        self.workspace = Workspace.objects.create(
            name="Concurrent Invitation Workspace",
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.Role.OWNER,
        )

    def test_concurrent_invitation_creation_does_not_duplicate(self):
        email = "concurrent-invitee@example.com"
        barrier = Barrier(2, timeout=15)

        def worker():
            close_old_connections()

            try:
                workspace = Workspace.objects.get(
                    pk=self.workspace.pk
                )
                owner = User.objects.get(
                    pk=self.owner.pk
                )

                barrier.wait()

                try:
                    invitation = create_workspace_invitation(
                        workspace=workspace,
                        invited_by=owner,
                        email=email,
                    )
                    return "created", invitation.pk

                except ValidationError:
                    return "validation_error", None

            finally:
                connections.close_all()

        with patch(
            "workspaces.services.send_workspace_invitation_email"
        ) as send_email:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(worker)
                    for _ in range(2)
                ]

                results = [
                    future.result(timeout=30)
                    for future in futures
                ]

        self.assertEqual(
            WorkspaceInvitation.objects.filter(
                workspace=self.workspace,
                email=email,
                status=WorkspaceInvitation.Status.PENDING,
            ).count(),
            1,
        )

        self.assertEqual(
            sum(
                status == "created"
                for status, _ in results
            ),
            1,
        )

        self.assertEqual(send_email.call_count, 1)

    def test_concurrent_invitation_creates_one_notification(self):
        email = "concurrent-registered@example.com"

        recipient = User.objects.create_user(
            email=email,
            password="TestPassword123!",
        )

        key = f"workspace_invited:"
        barrier = Barrier(2, timeout=15)

        def worker():
            close_old_connections()

            try:
                workspace = Workspace.objects.get(
                    pk=self.workspace.pk
                )
                owner = User.objects.get(
                    pk=self.owner.pk
                )

                barrier.wait()

                try:
                    invitation = create_workspace_invitation(
                        workspace=workspace,
                        invited_by=owner,
                        email=email,
                    )
                    return "created", invitation.pk

                except ValidationError:
                    return "validation_error", None

            finally:
                connections.close_all()

        with patch(
            "workspaces.services.send_workspace_invitation_email"
        ) as send_email:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(worker)
                    for _ in range(2)
                ]

                results = [
                    future.result(timeout=30)
                    for future in futures
                ]

        invitations = WorkspaceInvitation.objects.filter(
            workspace=self.workspace,
            email=email,
            status=WorkspaceInvitation.Status.PENDING,
        )

        self.assertEqual(invitations.count(), 1)

        invitation = invitations.get()

        notifications = Notification.objects.filter(
            recipient=recipient,
            event_type=Notification.EventType.WORKSPACE_INVITED,
            workspace=self.workspace,
        )

        self.assertEqual(notifications.count(), 1)

        notification = notifications.get()

        self.assertEqual(
            notification.deduplication_key,
            f"{key}{invitation.pk}:{recipient.pk}",
        )

        self.assertEqual(
            notification.payload,
            {"invitation_id": str(invitation.pk)},
        )

        self.assertEqual(
            sum(status == "created" for status, _ in results),
            1,
        )

        self.assertEqual(send_email.call_count, 1)

    def test_duplicate_constraint_error_becomes_validation_error(self):
        email = "constraint-test@example.com"

        def raise_duplicate_constraint(*args, **kwargs):
            cause = Exception("duplicate key")
            cause.diag = type(
                "Diagnostic",
                (),
                {
                    "constraint_name":
                        "unique_pending_ws_invitation_email"
                },
            )()

            error = IntegrityError("duplicate invitation")
            error.__cause__ = cause
            raise error

        with patch(
            "workspaces.services.WorkspaceInvitation.objects.create",
            side_effect=raise_duplicate_constraint,
        ):
            with self.assertRaises(ValidationError) as context:
                create_workspace_invitation(
                    workspace=self.workspace,
                    invited_by=self.owner,
                    email=email,
                )

        self.assertIn(
            "email",
            context.exception.detail,
        )

        self.assertFalse(
            WorkspaceInvitation.objects.filter(
                workspace=self.workspace,
                email=email,
            ).exists()
        )

    def test_unrelated_integrity_error_is_not_hidden(self):
        email = "unrelated-constraint@example.com"

        def raise_unrelated_constraint(*args, **kwargs):
            cause = Exception("other database error")
            cause.diag = type(
                "Diagnostic",
                (),
                {
                    "constraint_name": "some_other_constraint"
                },
            )()

            error = IntegrityError("unrelated constraint")
            error.__cause__ = cause
            raise error

        with patch(
            "workspaces.services.WorkspaceInvitation.objects.create",
            side_effect=raise_unrelated_constraint,
        ):
            with self.assertRaises(IntegrityError):
                create_workspace_invitation(
                    workspace=self.workspace,
                    invited_by=self.owner,
                    email=email,
                )
