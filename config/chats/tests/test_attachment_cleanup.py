
from unittest.mock import call, patch

from django.test import SimpleTestCase

from chats.services import cleanup_deleted_message_attachments


class ChatAttachmentCleanupTests(SimpleTestCase):

    @patch("chats.services.cleanup_deleted_attachment")
    @patch("chats.services.ChatAttachment")
    def test_successful_cleanup(
        self, attachment_model, cleanup_attachment
    ):
        queryset = attachment_model.objects.filter.return_value
        queryset.values_list.return_value = [
            "attachment-1",
            "attachment-2",
        ]

        cleanup_deleted_message_attachments("message-1")

        attachment_model.objects.filter.assert_called_once_with(
            message_id="message-1",
            message__deleted_at__isnull=False,
        )

        self.assertEqual(
            cleanup_attachment.call_args_list,
            [
                call("attachment-1"),
                call("attachment-2"),
            ],
        )

    @patch("chats.services.logger")
    @patch("chats.services.cleanup_deleted_attachment")
    @patch("chats.services.ChatAttachment")
    def test_cleanup_failure_is_logged_and_next_item_processed(
        self, attachment_model, cleanup_attachment, logger
    ):
        queryset = attachment_model.objects.filter.return_value
        queryset.values_list.return_value = [
            "attachment-1",
            "attachment-2",
        ]

        cleanup_attachment.side_effect = [
            OSError("Storage unavailable"),
            True,
        ]

        cleanup_deleted_message_attachments("message-1")

        self.assertEqual(cleanup_attachment.call_count, 2)
        logger.exception.assert_called_once()
