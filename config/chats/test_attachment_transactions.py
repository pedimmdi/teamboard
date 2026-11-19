from datetime import timedelta
from unittest.mock import patch
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.test import TransactionTestCase, override_settings

from chats.models import ChatAttachment, ChatMessage
from chats.services import (
    create_chat_message,
    delete_chat_message,
    get_or_create_direct_chat,
)
from chats.storage import chat_attachment_storage
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatAttachmentTransactionTests(TransactionTestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        settings_override = override_settings(
            CHAT_ATTACHMENT_ROOT=self.temp_dir.name
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.alice = User.objects.create_user(
            email="transaction-alice@example.com",
            password="Strong-password-2026!",
        )
        self.bob = User.objects.create_user(
            email="transaction-bob@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Chat Transaction Workspace"
        )

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.alice,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.bob,
            role=WorkspaceMembership.Role.MEMBER,
        )

        self.conversation = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.bob,
            actor=self.alice,
        )

    def create_message_with_attachment(self):
        return create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.conversation.pk,
            actor=self.alice,
            content="Transaction test",
            attachments=[
                SimpleUploadedFile(
                    "transaction.txt",
                    b"Transaction attachment",
                )
            ],
        )

    def test_real_commit_deletes_attachment(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )

        storage = chat_attachment_storage()
        key = attachment.storage_key

        self.assertTrue(storage.exists(key))

        with transaction.atomic():
            delete_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message.pk,
                actor=self.alice,
            )

            self.assertTrue(storage.exists(key))

        self.assertFalse(storage.exists(key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)

    def test_real_rollback_preserves_attachment(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )

        storage = chat_attachment_storage()
        key = attachment.storage_key

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                delete_chat_message(
                    workspace_slug=self.workspace.slug,
                    message_id=message.pk,
                    actor=self.alice,
                )

                raise RuntimeError("Force rollback")

        message.refresh_from_db()

        self.assertIsNone(message.deleted_at)
        self.assertTrue(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

    def test_create_rollback_leaves_recoverable_orphan(self):
        storage = chat_attachment_storage()

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                message = self.create_message_with_attachment()

                key = ChatAttachment.objects.get(
                    message=message
                ).storage_key

                self.assertTrue(storage.exists(key))

                raise RuntimeError("Force rollback")

        self.assertFalse(
            ChatMessage.objects.exists()
        )
        self.assertFalse(
            ChatAttachment.objects.exists()
        )

        # Storage is not transactional. This orphan must
        # be handled by the cleanup command.
        self.assertTrue(storage.exists(key))

    def mark_message_deleted(self, message, *, hours_ago=48):
        deleted_at = timezone.now() - timedelta(
            hours=hours_ago
        )

        ChatMessage.objects.filter(pk=message.pk).update(
            content="",
            deleted_at=deleted_at,
        )

    def test_cleanup_dry_run_preserves_deleted_message_attachment(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )
        key = attachment.storage_key
        storage = chat_attachment_storage()

        self.mark_message_deleted(message)

        call_command("cleanup_chat_attachments")

        self.assertTrue(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

    def test_cleanup_removes_old_deleted_message_attachment(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )
        key = attachment.storage_key
        storage = chat_attachment_storage()

        self.mark_message_deleted(message)

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertFalse(storage.exists(key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)

    def test_cleanup_preserves_recently_deleted_message_attachment(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )
        key = attachment.storage_key
        storage = chat_attachment_storage()

        self.mark_message_deleted(
            message,
            hours_ago=1,
        )

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertTrue(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

    def test_cleanup_storage_failure_preserves_metadata(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )
        key = attachment.storage_key
        storage = chat_attachment_storage()

        self.mark_message_deleted(message)

        with patch(
            "chats.attachment_cleanup.chat_attachment_storage",
            return_value=storage,
        ):
            with patch.object(
                storage,
                "delete",
                side_effect=OSError(
                    "Simulated storage failure"
                ),
            ):
                with self.assertRaises(CommandError):
                    call_command(
                        "cleanup_chat_attachments",
                        delete=True,
                    )

        self.assertTrue(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

    def test_cleanup_recovers_after_metadata_delete_failure(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )

        key = attachment.storage_key
        storage = chat_attachment_storage()

        self.mark_message_deleted(message)

        # Simulate a database failure after storage deletion.
        with patch.object(
            ChatAttachment,
            "delete",
            side_effect=RuntimeError(
                "Simulated metadata deletion failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                call_command(
                    "cleanup_chat_attachments",
                    delete=True,
                )

        # The file was deleted, but the database transaction
        # rolled back, so the metadata is still present.
        self.assertFalse(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        # A second cleanup run must recover safely.
        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertFalse(storage.exists(key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

    def test_cleanup_removes_metadata_when_file_is_missing(self):
        message = self.create_message_with_attachment()
        attachment = ChatAttachment.objects.get(
            message=message
        )

        storage = chat_attachment_storage()
        key = attachment.storage_key

        self.mark_message_deleted(message)

        # Simulate an attachment already removed from disk.
        storage.delete(key)

        self.assertFalse(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        # Repeated cleanup must remain safe.
        call_command(
            "cleanup_chat_attachments",
            delete=True,
        )

    def test_concurrent_cleanup_preserves_active_attachments(self):
        deleted_message = self.create_message_with_attachment()
        active_message = self.create_message_with_attachment()

        deleted_attachment = ChatAttachment.objects.get(
            message=deleted_message
        )
        active_attachment = ChatAttachment.objects.get(
            message=active_message
        )

        deleted_key = deleted_attachment.storage_key
        active_key = active_attachment.storage_key

        self.mark_message_deleted(deleted_message)

        storage = chat_attachment_storage()
        barrier = Barrier(2)

        def service_cleanup():
            from django.db import close_old_connections
            from chats.services import (
                cleanup_deleted_message_attachments,
            )

            close_old_connections()
            try:
                barrier.wait(timeout=10)
                cleanup_deleted_message_attachments(
                    deleted_message.pk
                )
            finally:
                close_old_connections()

        def command_cleanup():
            from django.db import close_old_connections

            close_old_connections()
            try:
                barrier.wait(timeout=10)
                call_command(
                    "cleanup_chat_attachments",
                    delete=True,
                    min_age_hours=24,
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            service_future = executor.submit(service_cleanup)
            command_future = executor.submit(command_cleanup)

            service_future.result(timeout=30)
            command_future.result(timeout=30)

        self.assertFalse(storage.exists(deleted_key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=deleted_attachment.pk
            ).exists()
        )

        self.assertTrue(storage.exists(active_key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=active_attachment.pk
            ).exists()
        )
