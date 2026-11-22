
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from comments.models import CommentAttachment
from comments.storage import attachment_storage


class AttachmentCleanupTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.settings_override = override_settings(
            COMMENT_ATTACHMENT_ROOT=self.temp_dir.name
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.storage = attachment_storage()

    def create_file(self, *, old=False, filename=None):
        filename = filename or uuid4().hex

        key = self.storage.save(
            f"uploads/{filename}",
            ContentFile(b"Test attachment"),
        )

        if old:
            old_timestamp = (
                timezone.now() - timedelta(hours=48)
            ).timestamp()

            os.utime(
                self.storage.path(key),
                (old_timestamp, old_timestamp),
            )

        return key

    def run_cleanup(self, *, execute=False):
        options = {"verbosity": 0}

        if execute:
            options["execute"] = True

        call_command(
            "cleanup_orphan_attachments",
            **options,
        )

    def test_dry_run_does_not_delete_old_orphan(self):
        key = self.create_file(old=True)

        self.run_cleanup()

        self.assertTrue(self.storage.exists(key))

    def test_execute_deletes_old_orphan(self):
        key = self.create_file(old=True)

        self.run_cleanup(execute=True)

        self.assertFalse(self.storage.exists(key))

    def test_execute_keeps_recent_orphan(self):
        key = self.create_file(old=False)

        self.run_cleanup(execute=True)

        self.assertTrue(self.storage.exists(key))

    def test_execute_ignores_unrecognized_filename(self):
        key = self.create_file(
            old=True,
            filename="cleanup_test.txt",
        )

        self.run_cleanup(execute=True)

        self.assertTrue(self.storage.exists(key))

    def test_execute_keeps_referenced_attachment(self):
        # Create an attachment record without requiring
        # a complete comment fixture by mocking the
        # database existence check.
        key = self.create_file(old=True)

        with patch(
            "comments.management.commands."
            "cleanup_orphan_attachments."
            "CommentAttachment.objects.filter"
        ) as mocked_filter:
            mocked_filter.return_value.exists.return_value = True

            self.run_cleanup(execute=True)

        self.assertTrue(self.storage.exists(key))

    def test_rejects_unsafe_minimum_age(self):
        with self.assertRaises(CommandError):
            call_command(
                "cleanup_orphan_attachments",
                min_age_hours=1,
            )

    def test_storage_delete_failure_is_reported(self):
        key = self.create_file(old=True)

        with patch.object(
            type(self.storage),
            "delete",
            side_effect=OSError("Storage failure"),
        ):
            with self.assertRaises(CommandError):
                self.run_cleanup(execute=True)

        self.assertTrue(self.storage.exists(key))
