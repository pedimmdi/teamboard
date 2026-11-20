"""Side effects run only in workers, serialized per outbox record."""
import logging
from billiard.exceptions import SoftTimeLimitExceeded
from datetime import timedelta
from smtplib import SMTPException, SMTPRecipientsRefused, SMTPResponseException, SMTPNotSupportedError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .models import BackgroundJob

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8


def email_is_current(data):
    guard = data.get("guard")
    if not guard:
        return True
    if guard["kind"] == "invitation":
        from workspaces.models import WorkspaceInvitation
        return WorkspaceInvitation.objects.filter(pk=guard["invitation_id"], token_hash=guard["token_hash"], status="pending", expires_at__gt=timezone.now()).exists()
    from django.contrib.auth import get_user_model
    from django.contrib.auth.tokens import default_token_generator, PasswordResetTokenGenerator
    user = get_user_model().objects.filter(pk=guard["user_id"], is_active=True, email__in=data["to"]).first()
    if user is None:
        return False
    if guard["kind"] == "verification":
        return not user.is_email_verified and default_token_generator.check_token(user, guard["token"])
    if guard["kind"] == "password_reset":
        return PasswordResetTokenGenerator().check_token(user, guard["token"])
    raise ValueError("Unknown email guard")


def perform(job):
    if job.kind == BackgroundJob.Kind.EMAIL:
        data = job.payload
        if not email_is_current(data):
            return
        if EmailMessage(data["subject"], data["body"], data["from_email"], data["to"], headers={"Message-ID": f"<{job.pk}@teamboard.local>"}).send(fail_silently=False) != 1:
            raise OSError("Email backend did not accept the message")
    elif job.kind == BackgroundJob.Kind.COMMENT_FILE:
        from comments.models import CommentAttachment
        from comments.storage import attachment_storage
        key = job.payload["key"]
        if not CommentAttachment.objects.filter(storage_key=key).exists():
            attachment_storage().delete(key)
    elif job.kind == BackgroundJob.Kind.CHAT_ATTACHMENT:
        from chats.attachment_cleanup import cleanup_deleted_attachment
        cleanup_deleted_attachment(job.payload["id"])
    else:
        raise ValueError("Unknown background job kind")


def execute_job(job_id):
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.state != BackgroundJob.State.PENDING:
            return "done"
        now = timezone.now()
        if job.expires_at <= now:
            job.state = BackgroundJob.State.FAILED
            job.last_error = "Expired"
            job.payload = {}
            job.save(update_fields=["state", "last_error", "payload"])
            return "done"
        if job.available_at > now:
            return "not_due"
        job.attempts += 1
        try:
            with transaction.atomic():
                perform(job)
        except Exception as exc:
            # Known transient I/O failures retry; invalid payload/programming
            # errors stop rather than creating a poison-message loop.
            retryable = isinstance(exc, (OSError, SMTPException, SoftTimeLimitExceeded))
            if isinstance(exc, SMTPResponseException):
                retryable = 400 <= exc.smtp_code < 500
            elif isinstance(exc, SMTPRecipientsRefused):
                retryable = any(400 <= code < 500 for code, _ in exc.recipients.values())
            elif isinstance(exc, SMTPNotSupportedError):
                retryable = False
            job.last_error = type(exc).__name__[:100]
            if retryable and job.attempts < MAX_ATTEMPTS:
                job.dispatched_at = None
                job.available_at = now + timedelta(seconds=min(3600, 30 * 2 ** (job.attempts - 1)))
                outcome = "retry"
            else:
                job.state = BackgroundJob.State.FAILED
                job.payload = {}
                outcome = "done"
            logger.warning("Background job failed job=%s kind=%s error=%s attempt=%s", job.pk, job.kind, job.last_error, job.attempts)
        else:
            job.state = BackgroundJob.State.DONE
            job.completed_at = timezone.now()
            job.payload = {}
            job.last_error = ""
            outcome = "done"
        job.save(update_fields=["attempts", "available_at", "state", "payload", "last_error", "completed_at", "dispatched_at"])
        return outcome
