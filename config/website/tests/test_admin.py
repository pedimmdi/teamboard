
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from website.admin import BlogPostAdmin, ContactMessageAdmin
from website.models import BlogPost, ContactMessage


User = get_user_model()


class WebsiteAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            email="website-superuser@example.com",
            password="Strong-test-password-2026!",
        )

        cls.staff = User.objects.create_user(
            email="website-staff@example.com",
            password="Strong-test-password-2026!",
        )
        cls.staff.is_staff = True
        cls.staff.save(update_fields=["is_staff"])

        cls.contact = ContactMessage.objects.create(
            name="Alex Johnson",
            email="alex@example.com",
            subject="Contact request",
            message="Original contact message.",
        )

        cls.draft = BlogPost.objects.create(
            title="First draft",
            slug="first-draft",
            excerpt="A draft article.",
            content="# Draft content",
            status=BlogPost.Status.DRAFT,
        )

    def contact_changelist_url(self):
        return reverse(
            "admin:website_contactmessage_changelist"
        )

    def contact_change_url(self):
        return reverse(
            "admin:website_contactmessage_change",
            args=[self.contact.pk],
        )

    def test_website_models_are_registered(self):
        self.assertIn(ContactMessage, admin.site._registry)
        self.assertIn(BlogPost, admin.site._registry)

        self.assertIsInstance(
            admin.site._registry[ContactMessage],
            ContactMessageAdmin,
        )
        self.assertIsInstance(
            admin.site._registry[BlogPost],
            BlogPostAdmin,
        )

    def test_unprivileged_staff_cannot_access_website_data(self):
        self.client.force_login(self.staff)

        contact_response = self.client.get(
            self.contact_changelist_url()
        )

        blog_response = self.client.get(
            reverse("admin:website_blogpost_changelist")
        )

        self.assertEqual(contact_response.status_code, 403)
        self.assertEqual(blog_response.status_code, 403)

    def test_superuser_can_view_private_contact_messages(self):
        self.client.force_login(self.superuser)

        list_response = self.client.get(
            self.contact_changelist_url()
        )

        detail_response = self.client.get(
            self.contact_change_url()
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)

        self.assertContains(
            detail_response,
            "Original contact message.",
        )

    def test_contact_messages_cannot_be_added_or_deleted(self):
        self.client.force_login(self.superuser)

        add_response = self.client.get(
            reverse("admin:website_contactmessage_add")
        )

        delete_response = self.client.get(
            reverse(
                "admin:website_contactmessage_delete",
                args=[self.contact.pk],
            )
        )

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_contact_admin_changes_only_status(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.contact_change_url(),
            {
                "name": "Tampered Name",
                "email": "tampered@example.com",
                "subject": "Tampered Subject",
                "message": "Tampered message.",
                "status": ContactMessage.Status.REVIEWED,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.contact.refresh_from_db()

        self.assertEqual(
            self.contact.status,
            ContactMessage.Status.REVIEWED,
        )
        self.assertEqual(self.contact.name, "Alex Johnson")
        self.assertEqual(
            self.contact.email,
            "alex@example.com",
        )
        self.assertEqual(
            self.contact.subject,
            "Contact request",
        )
        self.assertEqual(
            self.contact.message,
            "Original contact message.",
        )

    def test_staff_with_explicit_permissions_can_review_contact(self):
        permissions = Permission.objects.filter(
            content_type__app_label="website",
            codename__in=(
                "view_contactmessage",
                "change_contactmessage",
            ),
        )

        self.assertEqual(permissions.count(), 2)

        self.staff.user_permissions.add(*permissions)

        self.client.force_login(self.staff)

        response = self.client.get(
            self.contact_change_url()
        )

        self.assertEqual(response.status_code, 200)

        update_response = self.client.post(
            self.contact_change_url(),
            {
                "status": ContactMessage.Status.CLOSED,
                "_save": "Save",
            },
        )

        self.assertEqual(update_response.status_code, 302)

        self.contact.refresh_from_db()

        self.assertEqual(
            self.contact.status,
            ContactMessage.Status.CLOSED,
        )

    def test_superuser_can_create_blog_draft(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:website_blogpost_add"),
            {
                "title": "Teamboard announcement",
                "slug": "teamboard-announcement",
                "excerpt": "Our latest announcement.",
                "content": "# Announcement\n\nWelcome.",
                "status": BlogPost.Status.DRAFT,
                "published_at_0": "",
                "published_at_1": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        post = BlogPost.objects.get(
            slug="teamboard-announcement"
        )

        self.assertEqual(post.status, BlogPost.Status.DRAFT)
        self.assertIsNone(post.published_at)

    def test_admin_can_edit_and_publish_persian_translation(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:website_blogpost_change", args=[self.draft.pk])
        form_response = self.client.get(url)
        self.assertContains(form_response, 'dir="rtl" lang="fa"', count=3)

        publication = timezone.localtime() - timedelta(minutes=10)
        fields = {
            "title": self.draft.title,
            "slug": self.draft.slug,
            "content": self.draft.content,
            "title_fa": "راهنمای تیم‌برد",
            "excerpt_fa": "چگونه همکاری را شروع کنیم؟",
            "content_fa": "  \n",
            "status": BlogPost.Status.PUBLISHED,
            "published_at_0": publication.date().isoformat(),
            "published_at_1": publication.strftime("%H:%M:%S"),
            "_save": "Save",
        }
        self.assertRedirects(self.client.post(url, fields), reverse("admin:website_blogpost_changelist"))
        detail = reverse("website_api_v1:blog_detail", kwargs={"slug": self.draft.slug})
        self.assertFalse(self.client.get(detail, {"lang": "fa"}).json()["has_persian_translation"])

        fields["content_fa"] = "## شروع همکاری\n\nپروژه را بسازید."
        self.assertRedirects(self.client.post(url, fields), reverse("admin:website_blogpost_changelist"))
        article = self.client.get(detail, {"lang": "fa"}).json()
        self.assertEqual(article["title"], fields["title_fa"])
        self.assertEqual(article["content"], fields["content_fa"])

        fields["title_fa"] = "الف" * 201
        self.assertEqual(self.client.post(url, fields).status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title_fa, "راهنمای تیم‌برد")

    def test_admin_can_schedule_blog_publication(self):
        self.client.force_login(self.superuser)

        scheduled_at = timezone.now() + timedelta(days=2)

        response = self.client.post(
            reverse(
                "admin:website_blogpost_change",
                args=[self.draft.pk],
            ),
            {
                "title": self.draft.title,
                "slug": self.draft.slug,
                "excerpt": self.draft.excerpt,
                "content": self.draft.content,
                "status": BlogPost.Status.PUBLISHED,
                "published_at_0": scheduled_at.strftime(
                    "%Y-%m-%d"
                ),
                "published_at_1": scheduled_at.strftime(
                    "%H:%M:%S"
                ),
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.draft.refresh_from_db()

        self.assertEqual(
            self.draft.status,
            BlogPost.Status.PUBLISHED,
        )
        self.assertGreater(
            self.draft.published_at,
            timezone.now(),
        )

        # Scheduled articles must remain hidden publicly.
        public_response = self.client.get(
            reverse(
                "website_api_v1:blog_detail",
                kwargs={"slug": self.draft.slug},
            )
        )

        self.assertEqual(
            public_response.status_code,
            404,
        )

    def test_admin_rejects_publication_without_date(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse(
                "admin:website_blogpost_change",
                args=[self.draft.pk],
            ),
            {
                "title": self.draft.title,
                "slug": self.draft.slug,
                "excerpt": self.draft.excerpt,
                "content": self.draft.content,
                "status": BlogPost.Status.PUBLISHED,
                "published_at_0": "",
                "published_at_1": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.draft.refresh_from_db()

        self.assertEqual(
            self.draft.status,
            BlogPost.Status.DRAFT,
        )
        self.assertIsNone(self.draft.published_at)
