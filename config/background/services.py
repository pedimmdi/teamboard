import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import BackgroundJob

logger = logging.getLogger(__name__)


def dispatch(job_id):
    from .tasks import deliver_job
    try:
        deliver_job.delay(str(job_id))
        BackgroundJob.objects.filter(pk=job_id, state="pending").update(dispatched_at=timezone.now())
    except Exception as exc:
        # No synchronous fallback: durable pending work is recovered by Beat.
        # Log the error class, never SMTP content, tokens, or broker credentials.
        logger.error("Background dispatch failed job=%s error=%s", job_id, type(exc).__name__)


def enqueue(kind, payload, *, using="default"):
    ttl = timedelta(hours=1) if kind == BackgroundJob.Kind.EMAIL else timedelta(days=7)
    job = BackgroundJob.objects.using(using).create(kind=kind, payload=payload, expires_at=timezone.now() + ttl)
    transaction.on_commit(lambda: dispatch(job.pk), using=using, robust=True)
    return job


def enqueue_email(subject, message, from_email, recipient_list, fail_silently=False, guard=None):
    return enqueue(BackgroundJob.Kind.EMAIL, {
        "subject": subject, "body": message, "from_email": from_email,
        "to": list(recipient_list), "guard": guard,
    })


def enqueue_comment_file(key, *, using="default"):
    return enqueue(BackgroundJob.Kind.COMMENT_FILE, {"key": key}, using=using)


def enqueue_avatar_file(key, *, using="default"):
    return enqueue(BackgroundJob.Kind.AVATAR_FILE, {"key": key}, using=using)


def enqueue_chat_attachments(message_id):
    from chats.models import ChatAttachment
    for attachment_id in ChatAttachment.objects.filter(message_id=message_id).values_list("pk", flat=True):
        enqueue(BackgroundJob.Kind.CHAT_ATTACHMENT, {"id": str(attachment_id)})
