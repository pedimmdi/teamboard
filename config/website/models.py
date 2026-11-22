
import uuid

from django.db import models
from django.db.models import Q


class ContactMessage(models.Model):
    """
    A private contact submission from the public website.

    Submissions do not require a registered Teamboard user.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=180)
    message = models.TextField(max_length=5000)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.NEW,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="website_contact_status_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["new", "reviewed", "closed"]
                ),
                name="website_contact_status_valid",
            ),
        ]

    def __str__(self):
        return self.subject


class BlogPost(models.Model):
    """
    A simple editorial blog post.

    Public APIs must expose only published posts whose
    publication date has been reached.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=180,
        unique=True,
        allow_unicode=True,
    )

    excerpt = models.CharField(
        max_length=400,
        blank=True,
    )

    # Markdown text; never render as untrusted raw HTML.
    content = models.TextField(max_length=50000)
    title_fa = models.CharField(max_length=200, blank=True)
    excerpt_fa = models.CharField(max_length=400, blank=True)
    content_fa = models.TextField(max_length=50000, blank=True)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(
                fields=["status", "-published_at"],
                name="website_post_public_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["draft", "published"]
                ),
                name="website_post_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="published")
                    | Q(published_at__isnull=False)
                ),
                name="website_post_publish_date",
            ),
        ]

    @property
    def has_persian_translation(self):
        return bool(self.title_fa and self.content_fa)

    def __str__(self):
        return self.title
