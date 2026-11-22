
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from website.models import BlogPost, ContactMessage


def create_contact_message(*, name, email, subject, message):
    """
    Store a validated public contact submission.
    """
    return ContactMessage.objects.create(
        name=name,
        email=email,
        subject=subject,
        message=message,
    )


def get_public_blog_posts():
    """
    Return only published posts whose publication
    date has been reached.
    """
    return (
        BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )
        .order_by("-published_at", "-pk")
    )


def get_expired_contact_messages(*, days, now=None):
    """
    Select contact submissions past their retention period.
    """
    if not 1 <= days <= 3650:
        raise ValueError(
            "Retention days must be between 1 and 3650."
        )

    if now is None:
        now = timezone.now()

    cutoff = now - timedelta(days=days)

    return ContactMessage.objects.filter(
        created_at__lt=cutoff
    )


def purge_expired_contact_messages(*, days, now=None):
    """
    Delete expired messages in a transaction.

    Safe to run repeatedly. Returns the number
    of ContactMessage records deleted.
    """
    with transaction.atomic():
        expired = get_expired_contact_messages(
            days=days,
            now=now,
        )

        _, deleted_by_model = expired.delete()

    return deleted_by_model.get(
        ContactMessage._meta.label,
        0,
    )
