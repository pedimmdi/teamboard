
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from website.models import ContactMessage
from website.tasks import purge_expired_contact_messages


class ContactSchedulingTests(TestCase):

    def create_message(self, *, days_ago):
        message = ContactMessage.objects.create(
            name="Retention Test",
            email="retention@example.com",
            subject="Retention test",
            message="Test message.",
        )

        ContactMessage.objects.filter(
            pk=message.pk
        ).update(
            created_at=(
                timezone.now() - timedelta(days=days_ago)
            )
        )

        return message

    def test_daily_task_is_registered_in_beat_schedule(self):
        job = settings.CELERY_BEAT_SCHEDULE[
            "purge-website-contact-messages"
        ]

        self.assertEqual(
            job["task"],
            "website.tasks.purge_expired_contact_messages",
        )

        self.assertEqual(
            job["schedule"],
            86400.0,
        )

    @override_settings(
        WEBSITE_CONTACT_RETENTION_DAYS=180
    )
    def test_scheduled_task_removes_only_expired_messages(self):
        old = self.create_message(days_ago=200)
        recent = self.create_message(days_ago=20)

        deleted = purge_expired_contact_messages.run()

        self.assertEqual(deleted, 1)

        self.assertFalse(
            ContactMessage.objects.filter(
                pk=old.pk
            ).exists()
        )

        self.assertTrue(
            ContactMessage.objects.filter(
                pk=recent.pk
            ).exists()
        )

    @override_settings(
        WEBSITE_CONTACT_RETENTION_DAYS=7
    )
    def test_scheduled_task_uses_configured_retention(self):
        old = self.create_message(days_ago=10)
        recent = self.create_message(days_ago=2)

        deleted = purge_expired_contact_messages.run()

        self.assertEqual(deleted, 1)

        self.assertFalse(
            ContactMessage.objects.filter(
                pk=old.pk
            ).exists()
        )

        self.assertTrue(
            ContactMessage.objects.filter(
                pk=recent.pk
            ).exists()
        )

    @override_settings(
        WEBSITE_CONTACT_RETENTION_DAYS=180
    )
    def test_scheduled_task_is_idempotent(self):
        self.create_message(days_ago=200)

        first = purge_expired_contact_messages.run()
        second = purge_expired_contact_messages.run()

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

        self.assertEqual(
            ContactMessage.objects.count(),
            0,
        )

    @override_settings(
        WEBSITE_CONTACT_RETENTION_DAYS=7
    )
    def test_management_command_uses_configured_default(self):
        self.create_message(days_ago=10)

        output = StringIO()

        call_command(
            "purge_contact_messages",
            stdout=output,
        )

        self.assertIn(
            "older than 7 day(s)",
            output.getvalue(),
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            1,
        )
