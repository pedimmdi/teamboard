
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from website.models import BlogPost, ContactMessage


class ContactMessageModelTests(TestCase):
    def test_contact_message_defaults_to_new(self):
        message = ContactMessage.objects.create(
            name="Alex",
            email="alex@example.com",
            subject="General question",
            message="I would like to learn more about Teamboard.",
        )

        self.assertIsNotNone(message.pk)
        self.assertEqual(
            message.status,
            ContactMessage.Status.NEW,
        )
        self.assertIsNotNone(message.created_at)
        self.assertIsNotNone(message.updated_at)

    def test_contact_message_validates_email(self):
        message = ContactMessage(
            name="Alex",
            email="invalid-email",
            subject="Question",
            message="Hello Teamboard.",
        )

        with self.assertRaises(ValidationError):
            message.full_clean()

    def test_invalid_contact_status_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ContactMessage.objects.create(
                    name="Alex",
                    email="alex@example.com",
                    subject="Question",
                    message="Hello.",
                    status="invalid",
                )


class BlogPostModelTests(TestCase):
    def test_blog_post_defaults_to_draft(self):
        post = BlogPost.objects.create(
            title="Welcome to Teamboard",
            slug="welcome-to-teamboard",
            excerpt="Introducing Teamboard.",
            content="# Welcome\n\nThis is our first post.",
        )

        self.assertEqual(
            post.status,
            BlogPost.Status.DRAFT,
        )
        self.assertIsNone(post.published_at)

    def test_published_blog_post_requires_publication_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BlogPost.objects.create(
                    title="Invalid publication",
                    slug="invalid-publication",
                    content="Post content.",
                    status=BlogPost.Status.PUBLISHED,
                )

    def test_published_blog_post_with_date_is_valid(self):
        published_at = timezone.now()

        post = BlogPost.objects.create(
            title="Product update",
            slug="product-update",
            content="A new update is available.",
            status=BlogPost.Status.PUBLISHED,
            published_at=published_at,
        )

        self.assertEqual(
            post.status,
            BlogPost.Status.PUBLISHED,
        )
        self.assertEqual(
            post.published_at,
            published_at,
        )

    def test_blog_slug_must_be_unique(self):
        BlogPost.objects.create(
            title="First article",
            slug="first-article",
            content="First post.",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BlogPost.objects.create(
                    title="Duplicate article",
                    slug="first-article",
                    content="Second post.",
                )
