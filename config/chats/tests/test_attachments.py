from django.db import transaction
from chats.services import delete_chat_message
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chats.models import ChatAttachment, ChatMessage
from chats.storage import chat_attachment_storage
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class ChatAttachmentAPITests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        settings_override = override_settings(
            CHAT_ATTACHMENT_ROOT=self.temp_dir.name,
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.alice = User.objects.create_user(
            email="attachment-alice@example.com",
            password="Strong-password-2026!",
        )
        self.bob = User.objects.create_user(
            email="attachment-bob@example.com",
            password="Strong-password-2026!",
        )
        self.admin = User.objects.create_user(
            email="attachment-admin@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Attachment Workspace",
        )

        for user, role in (
            (self.alice, WorkspaceMembership.Role.OWNER),
            (self.bob, WorkspaceMembership.Role.MEMBER),
            (self.admin, WorkspaceMembership.Role.ADMIN),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

        direct_url = reverse(
            "workspaces_api_v1:chats_api_v1:direct-list-create",
            kwargs={"slug": self.workspace.slug},
        )
        response = self.client.post(
            direct_url,
            {"recipient_id": self.bob.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.conversation_id = response.data["id"]

        self.messages_url = reverse(
            "workspaces_api_v1:chats_api_v1:message-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "conversation_id": self.conversation_id,
            },
        )

    def upload(self, *, content="Hello", files=None):
        data = {"content": content}
        if files is not None:
            data["attachments"] = files

        return self.client.post(
            self.messages_url,
            data,
            format="multipart",
        )

    def download_url(self, message_id, attachment_id):
        return reverse(
            "workspaces_api_v1:chats_api_v1:attachment-download",
            kwargs={
                "slug": self.workspace.slug,
                "conversation_id": self.conversation_id,
                "message_id": message_id,
                "attachment_id": attachment_id,
            },
        )

    def test_multiple_files_upload_and_authorized_download(self):
        response = self.upload(
            files=[
                SimpleUploadedFile("one.txt", b"First file"),
                SimpleUploadedFile("two.txt", b"Second file"),
            ],
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["attachments"]), 2)

        message_id = response.data["id"]
        attachment = ChatAttachment.objects.filter(
            message_id=message_id,
        ).first()

        self.client.force_authenticate(user=self.bob)
        download = self.client.get(
            self.download_url(message_id, attachment.pk)
        )

        self.assertEqual(download.status_code, 200)
        self.assertEqual(
            b"".join(download.streaming_content),
            b"First file",
        )

    def test_admin_cannot_download_private_direct_file(self):
        response = self.upload(
            files=[
                SimpleUploadedFile("private.txt", b"Secret"),
            ],
        )
        self.assertEqual(response.status_code, 201)

        attachment = ChatAttachment.objects.get(
            message_id=response.data["id"]
        )

        self.client.force_authenticate(user=self.admin)

        download = self.client.get(
            self.download_url(response.data["id"], attachment.pk)
        )
        self.assertEqual(download.status_code, 404)

    def test_deleted_message_attachment_is_not_downloadable(self):
        response = self.upload(
            files=[
                SimpleUploadedFile("deleted.txt", b"Deleted file"),
            ],
        )
        self.assertEqual(response.status_code, 201)

        message_id = response.data["id"]
        attachment = ChatAttachment.objects.get(
            message_id=message_id
        )

        detail_url = reverse(
            "workspaces_api_v1:chats_api_v1:message-detail",
            kwargs={
                "slug": self.workspace.slug,
                "conversation_id": self.conversation_id,
                "message_id": message_id,
            },
        )

        self.assertEqual(
            self.client.delete(detail_url).status_code,
            204,
        )

        self.assertEqual(
            self.client.get(
                self.download_url(message_id, attachment.pk)
            ).status_code,
            404,
        )

    def test_invalid_attachment_creates_no_message(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(
                    "malicious.exe",
                    b"not allowed",
                ),
            ],
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())
        self.assertFalse(ChatAttachment.objects.exists())

    def test_attachment_only_message(self):
        response = self.upload(
            content="",
            files=[
                SimpleUploadedFile("only.txt", b"File only"),
            ],
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["content"], "")
        self.assertEqual(len(response.data["attachments"]), 1)

    def test_more_than_five_files_is_rejected(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(f"{i}.txt", b"Test")
                for i in range(6)
            ],
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_missing_file_returns_404(self):
        response = self.upload(
            files=[
                SimpleUploadedFile("missing.txt", b"Content"),
            ],
        )
        self.assertEqual(response.status_code, 201)

        attachment = ChatAttachment.objects.get(
            message_id=response.data["id"]
        )
        chat_attachment_storage().delete(
            attachment.storage_key
        )

        self.assertEqual(
            self.client.get(
                self.download_url(
                    response.data["id"],
                    attachment.pk,
                )
            ).status_code,
            404,
        )

    def test_removed_member_cannot_download_attachment(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(
                    "confidential.txt",
                    b"Confidential information",
                ),
            ],
        )
        self.assertEqual(response.status_code, 201)

        attachment = ChatAttachment.objects.get(
            message_id=response.data["id"],
        )

        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.bob,
        ).delete()

        self.client.force_authenticate(user=self.bob)

        download = self.client.get(
            self.download_url(
                response.data["id"],
                attachment.pk,
            )
        )

        self.assertEqual(download.status_code, 404)

    def test_attachment_deleted_only_after_commit(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(
                    "commit.txt", b"Commit test"
                ),
            ],
        )
        self.assertEqual(response.status_code, 201)

        message_id = response.data["id"]
        attachment = ChatAttachment.objects.get(
            message_id=message_id
        )
        storage = chat_attachment_storage()
        key = attachment.storage_key

        self.assertTrue(storage.exists(key))

        with self.captureOnCommitCallbacks(
            execute=True
        ) as callbacks:
            delete_chat_message(
                workspace_slug=self.workspace.slug,
                message_id=message_id,
                actor=self.alice,
            )

            self.assertTrue(storage.exists(key))
            self.assertTrue(
                ChatAttachment.objects.filter(
                    pk=attachment.pk
                ).exists()
            )

        self.assertEqual(len(callbacks), 2)
        self.assertFalse(storage.exists(key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        message = ChatMessage.objects.get(pk=message_id)
        self.assertIsNotNone(message.deleted_at)

    def test_rollback_preserves_attachment_and_message(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(
                    "rollback.txt", b"Rollback test"
                ),
            ],
        )
        self.assertEqual(response.status_code, 201)

        message_id = response.data["id"]
        attachment = ChatAttachment.objects.get(
            message_id=message_id
        )
        storage = chat_attachment_storage()
        key = attachment.storage_key

        with self.captureOnCommitCallbacks(
            execute=True
        ) as callbacks:
            try:
                with transaction.atomic():
                    delete_chat_message(
                        workspace_slug=self.workspace.slug,
                        message_id=message_id,
                        actor=self.alice,
                    )

                    self.assertIsNotNone(
                        ChatMessage.objects.get(
                            pk=message_id
                        ).deleted_at
                    )

                    raise RuntimeError(
                        "Simulated transaction rollback"
                    )
            except RuntimeError:
                pass

        self.assertEqual(len(callbacks), 0)
        self.assertTrue(storage.exists(key))
        self.assertTrue(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )

        message = ChatMessage.objects.get(pk=message_id)
        self.assertIsNone(message.deleted_at)

    def test_repeated_delete_is_idempotent(self):
        response = self.upload(
            files=[
                SimpleUploadedFile(
                    "repeat.txt", b"Repeat test"
                ),
            ],
        )
        self.assertEqual(response.status_code, 201)

        message_id = response.data["id"]
        attachment = ChatAttachment.objects.get(
            message_id=message_id
        )
        storage = chat_attachment_storage()
        key = attachment.storage_key

        with self.captureOnCommitCallbacks(
            execute=True
        ) as callbacks:
            for _ in range(2):
                delete_chat_message(
                    workspace_slug=self.workspace.slug,
                    message_id=message_id,
                    actor=self.alice,
                )

        self.assertEqual(len(callbacks), 2)
        self.assertFalse(storage.exists(key))
        self.assertFalse(
            ChatAttachment.objects.filter(
                pk=attachment.pk
            ).exists()
        )
