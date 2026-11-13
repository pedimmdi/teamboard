import os
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from .models import CommentAttachment
from .services import create_comment
from .storage import attachment_storage
from .test_api import CommentAPIFixture


class AttachmentCleanupTests(CommentAPIFixture):
    def setUp(self):
        super().setUp()
        self.enterContext(override_settings(COMMENT_ATTACHMENT_ROOT=self.enterContext(TemporaryDirectory())))
        self.storage = attachment_storage()

    def age(self, key):
        stamp = (timezone.now() - timedelta(days=2)).timestamp()
        os.utime(self.storage.path(key), (stamp, stamp))

    def upload(self):
        return create_comment(task=self.task, actor=self.member, body="Notes",
                              attachment=SimpleUploadedFile("notes.txt", b"notes"))

    def test_cleanup_recovers_outer_rollback_and_preserves_referenced_files(self):
        with transaction.atomic():
            rolled_back = self.upload().attachment.storage_key
            transaction.set_rollback(True)
        referenced = self.upload().attachment.storage_key
        self.assertFalse(CommentAttachment.objects.filter(storage_key=rolled_back).exists())
        call_command("cleanup_comment_attachments", apply=True)
        self.assertTrue(self.storage.exists(rolled_back))
        self.age(rolled_back)
        self.age(referenced)
        call_command("cleanup_comment_attachments")
        self.assertTrue(self.storage.exists(rolled_back))
        call_command("cleanup_comment_attachments", apply=True)
        self.assertFalse(self.storage.exists(rolled_back))
        self.assertTrue(self.storage.exists(referenced))

    def test_failed_delete_is_logged_and_cleanup_retries(self):
        comment = self.upload()
        key = comment.attachment.storage_key
        self.age(key)
        with patch("comments.signals.attachment_storage", return_value=self.storage):
            with patch.object(self.storage, "delete", side_effect=PermissionError):
                with self.assertLogs("comments.signals", level="ERROR"):
                    with self.captureOnCommitCallbacks(execute=True):
                        comment.delete()
        self.assertTrue(self.storage.exists(key))
        call_command("cleanup_comment_attachments", apply=True)
        self.assertFalse(self.storage.exists(key))


class LegacyAttachmentMigrationTests(TransactionTestCase):
    def test_interrupted_copy_reuses_existing_bytes_on_retry(self):
        self.enterContext(override_settings(COMMENT_ATTACHMENT_ROOT=self.enterContext(TemporaryDirectory())))
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [node for node in latest if node[0] != "comments"]
        previous.append(("comments", "0002_comment_edited_at_comment_mentions_comment_reply_to_and_more"))
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            workspace = apps.get_model("workspaces", "Workspace").objects.create(name="Legacy")
            user = apps.get_model("accounts", "User").objects.create(email="legacy@example.com")
            apps.get_model("workspaces", "WorkspaceMembership").objects.create(
                workspace=workspace, user=user, role="owner",
            )
            with transaction.atomic():
                project = apps.get_model("projects", "Project").objects.create(workspace=workspace, name="Legacy")
                apps.get_model("projects", "ProjectMembership").objects.create(
                    project=project, user=user, role="manager",
                )
            task = apps.get_model("tasks", "Task").objects.create(project=project, title="Legacy")
            Comment = apps.get_model("comments", "Comment")
            Attachment = apps.get_model("comments", "CommentAttachment")
            first = Attachment.objects.create(comment=Comment.objects.create(task=task), filename="first.txt", size=5, content=b"first")
            second = Attachment.objects.create(comment=Comment.objects.create(task=task), filename="second.txt", size=6, content=b"second")
            storage = attachment_storage()
            first_key = f"legacy/{first.comment_id.hex}"
            second_key = f"legacy/{second.comment_id.hex}"
            storage.save(second_key, ContentFile(b"conflict"))
            try:
                with self.assertRaisesRegex(RuntimeError, "storage conflict"):
                    MigrationExecutor(connection).migrate(latest)
                self.assertTrue(storage.exists(first_key))
                self.assertEqual(bytes(Attachment.objects.get(pk=first.pk).content), b"first")
            finally:
                storage.delete(second_key)
            MigrationExecutor(connection).migrate(latest)
            for row, key, expected in ((first, first_key, b"first"), (second, second_key, b"second")):
                self.assertEqual(CommentAttachment.objects.get(pk=row.pk).storage_key, key)
                with storage.open(key, "rb") as copied:
                    self.assertEqual(copied.read(), expected)
        finally:
            MigrationExecutor(connection).migrate(latest)
