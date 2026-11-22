
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from website.models import ContactMessage


class ContactRetentionTests(TestCase):
    def setUp(self):
        self.old = self.create_message(
            "old", days_ago=200
        )
        self.very_old = self.create_message(
            "very-old", days_ago=400,
            status=ContactMessage.Status.CLOSED,
        )
        self.recent = self.create_message(
            "recent", days_ago=30
        )
        self.current = self.create_message(
            "current", days_ago=0
        )

    def create_message(
        self,
        label,
        *,
        days_ago,
        status=ContactMessage.Status.NEW,
    ):
        message = ContactMessage.objects.create(
            name=label,
            email=f"{label}@example.com",
            subject=f"{label} contact",
            message=f"Contact message from {label}.",
            status=status,
        )

        ContactMessage.objects.filter(
            pk=message.pk
        ).update(
            created_at=(
                timezone.now() - timedelta(days=days_ago)
            )
        )

        return message

    def test_default_execution_is_dry_run(self):
        output = StringIO()

        call_command(
            "purge_contact_messages",
            stdout=output,
        )

        self.assertIn("DRY RUN: 2", output.getvalue())

        self.assertEqual(
            ContactMessage.objects.count(),
            4,
        )

    def test_execute_deletes_only_expired_messages(self):
        output = StringIO()

        call_command(
            "purge_contact_messages",
            execute=True,
            stdout=output,
        )

        remaining_ids = set(
            ContactMessage.objects.values_list(
                "pk", flat=True
            )
        )

        self.assertEqual(
            remaining_ids,
            {self.recent.pk, self.current.pk},
        )

        self.assertIn(
            "Deleted 2 contact message(s)",
            output.getvalue(),
        )

        self.assertNotIn(
            "old@example.com",
            output.getvalue(),
        )

    def test_custom_retention_period(self):
        call_command(
            "purge_contact_messages",
            days=20,
            execute=True,
            stdout=StringIO(),
        )

        remaining_ids = set(
            ContactMessage.objects.values_list(
                "pk", flat=True
            )
        )

        self.assertEqual(
            remaining_ids,
            {self.current.pk},
        )

    def test_invalid_retention_period_is_rejected(self):
        for days in (0, -1, 3651):
            with self.subTest(days=days):
                with self.assertRaises(CommandError):
                    call_command(
                        "purge_contact_messages",
                        days=days,
                        execute=True,
                        stdout=StringIO(),
                    )

        self.assertEqual(
            ContactMessage.objects.count(),
            4,
        )

    def test_command_is_idempotent(self):
        call_command(
            "purge_contact_messages",
            execute=True,
            stdout=StringIO(),
        )

        second_output = StringIO()

        call_command(
            "purge_contact_messages",
            execute=True,
            stdout=second_output,
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            2,
        )

        self.assertIn(
            "Deleted 0 contact message(s)",
            second_output.getvalue(),
        )
