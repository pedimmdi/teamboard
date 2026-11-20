from datetime import timedelta
from smtplib import SMTPDataError, SMTPServerDisconnected
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core import mail
from django.core.files.base import ContentFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from background.execution import execute_job, MAX_ATTEMPTS
from background.models import BackgroundJob
from background.services import enqueue_email, enqueue_comment_file, dispatch
from background.tasks import recover_pending_jobs


class BackgroundJobTests(TestCase):
    def setUp(self):
        self.dispatcher = self.enterContext(patch("background.services.dispatch"))
        self.enterContext(override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"))

    def email(self):
        return enqueue_email("Subject", "Private token: never log", "sender@example.com", ["recipient@example.com"])

    def test_enqueue_is_durable_before_commit_and_publish_waits(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                job = self.email()
                self.assertTrue(BackgroundJob.objects.filter(pk=job.pk).exists())
                self.dispatcher.assert_not_called()
        self.dispatcher.assert_called_once_with(job.pk)

    def test_outer_rollback_removes_job_and_publication(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                job = self.email()
                transaction.set_rollback(True)
        self.assertFalse(BackgroundJob.objects.filter(pk=job.pk).exists())
        self.dispatcher.assert_not_called()

    def test_duplicate_delivery_sends_only_once_and_redacts_content(self):
        job = self.email()
        self.assertEqual(execute_job(job.pk), "done")
        self.assertEqual(execute_job(job.pk), "done")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].extra_headers["Message-ID"], f"<{job.pk}@teamboard.local>")
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.payload, {})
        self.assertEqual(job.state, "done")

    def test_transient_failure_is_persisted_and_retry_succeeds(self):
        job = self.email()
        with patch("background.execution.EmailMessage.send", side_effect=SMTPServerDisconnected("private server detail")):
            with self.assertLogs("background.execution") as logs:
                self.assertEqual(execute_job(job.pk), "retry")
        self.assertNotIn("private server detail", " ".join(logs.output))
        self.assertNotIn("Private token", " ".join(logs.output))
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.state, "pending")
        self.assertGreater(job.available_at, timezone.now())
        self.assertEqual(execute_job(job.pk), "not_due")
        BackgroundJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
        self.assertEqual(execute_job(job.pk), "done")
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_status_codes_distinguish_temporary_and_permanent_failure(self):
        for code, expected in ((450, "retry"), (550, "done")):
            job = self.email()
            with patch("background.execution.EmailMessage.send", side_effect=SMTPDataError(code, b"private")):
                self.assertEqual(execute_job(job.pk), expected)
            job.refresh_from_db()
            self.assertEqual(job.state, "pending" if code == 450 else "failed")
            if code == 550:
                self.assertEqual(job.payload, {})

    def test_retry_budget_and_expiry_remove_sensitive_payloads(self):
        job = self.email()
        BackgroundJob.objects.filter(pk=job.pk).update(attempts=MAX_ATTEMPTS - 1)
        with patch("background.execution.EmailMessage.send", side_effect=OSError):
            execute_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.payload, {})
        expired = self.email()
        BackgroundJob.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        execute_job(expired.pk)
        expired.refresh_from_db()
        self.assertEqual(expired.last_error, "Expired")
        self.assertEqual(expired.payload, {})

    def test_broker_outage_does_not_lose_work_or_send_synchronously(self):
        job = self.email()
        with patch("background.tasks.deliver_job.delay", side_effect=OSError("credentials must not appear")):
            with self.assertLogs("background.services") as logs:
                dispatch(job.pk)
        self.assertNotIn("credentials must not appear", " ".join(logs.output))
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.attempts, 0)
        self.assertEqual(len(mail.outbox), 0)
        recover_pending_jobs()
        self.dispatcher.assert_called_once_with(job.pk)

    def test_broker_payload_contains_only_job_id(self):
        job = self.email()
        with patch("background.tasks.deliver_job.delay") as publish:
            dispatch(job.pk)
        publish.assert_called_once_with(str(job.pk))

    def test_recovery_expires_payloads_and_prunes_only_old_terminal_records(self):
        expired = self.email()
        retained = self.email()
        old_done = self.email()
        BackgroundJob.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        BackgroundJob.objects.filter(pk=old_done.pk).update(state="done", payload={}, created_at=timezone.now() - timedelta(days=8))
        recover_pending_jobs()
        expired.refresh_from_db()
        self.assertEqual(expired.payload, {})
        self.assertEqual(expired.state, "failed")
        self.assertTrue(BackgroundJob.objects.filter(pk=retained.pk).exists())
        self.assertFalse(BackgroundJob.objects.filter(pk=old_done.pk).exists())
        self.dispatcher.assert_called_once_with(retained.pk)

    def test_file_cleanup_is_idempotent_and_preserves_referenced_keys(self):
        from comments.storage import attachment_storage
        with TemporaryDirectory() as root, override_settings(COMMENT_ATTACHMENT_ROOT=root):
            storage = attachment_storage()
            key = storage.save("uploads/unreferenced", ContentFile(b"private file"))
            job = enqueue_comment_file(key)
            self.assertTrue(storage.exists(key))
            execute_job(job.pk)
            execute_job(job.pk)
            self.assertFalse(storage.exists(key))
            key = storage.save("uploads/referenced", ContentFile(b"keep"))
            job = enqueue_comment_file(key)
            with patch("comments.models.CommentAttachment.objects.filter") as references:
                references.return_value.exists.return_value = True
                execute_job(job.pk)
            self.assertTrue(storage.exists(key))

    def test_invalidated_account_emails_are_not_delivered(self):
        from accounts.models import User
        from accounts.api.v1.serializers import send_verification_email
        user = User.objects.create_user(email="verify-outbox@example.com")
        send_verification_email(user)
        job = BackgroundJob.objects.get()
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        execute_job(job.pk)
        self.assertEqual(len(mail.outbox), 0)
        job.refresh_from_db()
        self.assertEqual(job.state, "done")
        self.assertEqual(job.payload, {})

    def test_poison_payload_stops_without_retry_loop(self):
        job = self.email()
        BackgroundJob.objects.filter(pk=job.pk).update(payload={})
        execute_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.last_error, "KeyError")

    def test_recovery_respects_recent_dispatch_and_recovers_lost_delivery(self):
        recent, lost = self.email(), self.email()
        BackgroundJob.objects.filter(pk=recent.pk).update(dispatched_at=timezone.now())
        BackgroundJob.objects.filter(pk=lost.pk).update(dispatched_at=timezone.now() - timedelta(minutes=11))
        recover_pending_jobs()
        self.dispatcher.assert_called_once_with(lost.pk)

    def test_dispatch_records_lease_only_after_successful_publication(self):
        job = self.email()
        with patch("background.tasks.deliver_job.delay"):
            dispatch(job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.dispatched_at)

    def test_password_change_invalidates_queued_reset_email(self):
        from accounts.models import User
        from django.contrib.auth.tokens import PasswordResetTokenGenerator
        user = User.objects.create_user(email="reset-outbox@example.com", password="Original-password-2026!")
        token = PasswordResetTokenGenerator().make_token(user)
        job = enqueue_email("Reset", "Private reset URL", "sender@example.com", [user.email], guard={"kind": "password_reset", "user_id": user.pk, "token": token})
        user.set_password("Changed-password-2026!")
        user.save(update_fields=["password"])
        execute_job(job.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_resending_invitation_skips_old_queued_link(self):
        from accounts.models import User
        from workspaces.models import Workspace, WorkspaceMembership
        from workspaces.services import create_workspace_invitation, resend_workspace_invitation
        owner = User.objects.create_user(email="invite-outbox@example.com")
        workspace = Workspace.objects.create(name="Invitation outbox")
        WorkspaceMembership.objects.create(workspace=workspace, user=owner, role="owner")
        invitation = create_workspace_invitation(workspace=workspace, invited_by=owner, email="guest@example.com")
        first = BackgroundJob.objects.get()
        resend_workspace_invitation(workspace=workspace, invitation_id=invitation.pk, invited_by=owner)
        second = BackgroundJob.objects.exclude(pk=first.pk).get()
        execute_job(first.pk)
        self.assertEqual(len(mail.outbox), 0)
        execute_job(second.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_soft_time_limit_is_retryable(self):
        from billiard.exceptions import SoftTimeLimitExceeded
        job = self.email()
        with patch("background.execution.perform", side_effect=SoftTimeLimitExceeded):
            self.assertEqual(execute_job(job.pk), "retry")
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")

    def test_status_command_exposes_only_sanitized_metadata(self):
        from django.core.management import call_command, CommandError
        from io import StringIO
        import json
        job = self.email()
        BackgroundJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(hours=1))
        output = StringIO()
        call_command("background_status", stdout=output)
        status = json.loads(output.getvalue())
        self.assertEqual(status["counts"]["pending"], 1)
        self.assertGreaterEqual(status["oldest_pending_seconds"], 3600)
        self.assertNotIn("Private token", output.getvalue())
        self.assertNotIn("recipient@example.com", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("background_status", max_pending_age=60, stdout=StringIO())
