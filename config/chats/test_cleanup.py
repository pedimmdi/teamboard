
import os
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from chats.storage import chat_attachment_storage


class ChatAttachmentCleanupTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        override = override_settings(
            CHAT_ATTACHMENT_ROOT=self.temp_dir.name
        )
        override.enable()
        self.addCleanup(override.disable)

    def create_file(self, name, *, old=True):
        storage = chat_attachment_storage()
        path = storage.path(f"uploads/{name}")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as file:
            file.write(b"orphan content")

        if old:
            timestamp = (
                timezone.now() - timedelta(hours=48)
            ).timestamp()
            os.utime(path, (timestamp, timestamp))

        return path

    def test_rejects_unsafe_minimum_age(self):
        with self.assertRaises(CommandError):
            call_command(
                "cleanup_chat_attachments",
                min_age_hours=1,
            )

    @patch("chats.management.commands.cleanup_chat_attachments.ChatAttachment.objects")
    def test_dry_run_does_not_delete(self, objects):
        objects.filter.return_value.exists.return_value = False

        path = self.create_file("old-orphan")

        call_command("cleanup_chat_attachments")

        self.assertTrue(os.path.exists(path))

    @patch("chats.management.commands.cleanup_chat_attachments.ChatAttachment.objects")
    def test_delete_removes_old_orphan(self, objects):
        objects.filter.return_value.exists.return_value = False

        path = self.create_file("old-orphan")

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertFalse(os.path.exists(path))

    @patch("chats.management.commands.cleanup_chat_attachments.ChatAttachment.objects")
    def test_recent_orphan_is_not_deleted(self, objects):
        objects.filter.return_value.exists.return_value = False

        path = self.create_file(
            "recent-orphan",
            old=False,
        )

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertTrue(os.path.exists(path))

    @patch("chats.management.commands.cleanup_chat_attachments.ChatAttachment.objects")
    def test_registered_file_is_not_deleted(self, objects):
        objects.filter.return_value.exists.return_value = True

        path = self.create_file("registered-file")

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertTrue(os.path.exists(path))
