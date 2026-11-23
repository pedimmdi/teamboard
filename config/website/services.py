
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, F, Q, When
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


def get_public_blog_translations():
    return get_public_blog_posts().annotate(
        translation_available=~Q(title_fa="") & ~Q(content_fa=""),
    )


def get_public_blog_projection(*, persian, detail=False):
    posts = get_public_blog_translations()
    if persian and not detail:
        posts = posts.filter(translation_available=True)

    def localized(field):
        if not persian:
            return F(field)
        translation = F(f"{field}_fa")
        if not detail:
            return translation
        return Case(When(translation_available=True, then=translation), default=F(field))

    projection = {
        "public_title": localized("title"),
        "public_excerpt": localized("excerpt"),
    }
    if detail:
        projection["public_content"] = localized("content")
    return posts.values(
        "id", "slug", "published_at", "updated_at", "translation_available", **projection,
    )


def get_public_sitemap_projection():
    return get_public_blog_translations().values(
        "slug", "published_at", "updated_at", "translation_available", "pk",
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
