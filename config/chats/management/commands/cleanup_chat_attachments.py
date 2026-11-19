from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from chats.models import ChatAttachment
from chats.storage import chat_attachment_storage
from chats.attachment_cleanup import cleanup_deleted_attachment


class Command(BaseCommand):
    help = (
        "Find or clean orphaned chat files and attachments "
        "belonging to deleted messages."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete eligible files.",
        )
        parser.add_argument(
            "--min-age-hours",
            type=int,
            default=24,
            help="Minimum age in hours (default: 24).",
        )

    def handle(self, *args, **options):
        min_age_hours = options["min_age_hours"]

        if min_age_hours < 24:
            raise CommandError(
                "Minimum age must be at least 24 hours."
            )

        storage = chat_attachment_storage()
        cutoff = timezone.now() - timedelta(
            hours=min_age_hours
        )
        should_delete = options["delete"]

        scanned = 0
        orphaned = 0
        deleted = 0
        skipped_recent = 0
        deleted_message_attachments = 0
        metadata_removed = 0

        # Phase 1: Files without database records.
        try:
            directories, filenames = storage.listdir("uploads")
        except FileNotFoundError:
            directories, filenames = [], []

        if directories:
            raise CommandError(
                "Unexpected nested directories inside uploads."
            )

        for filename in filenames:
            key = f"uploads/{filename}"
            scanned += 1

            if ChatAttachment.objects.filter(
                storage_key=key
            ).exists():
                continue

            try:
                modified = storage.get_modified_time(key)
            except FileNotFoundError:
                continue

            if modified > cutoff:
                skipped_recent += 1
                continue

            orphaned += 1

            if not should_delete:
                self.stdout.write(f"Orphan: {key}")
                continue

            # Recheck metadata and file age immediately
            # before physical deletion.
            if ChatAttachment.objects.filter(
                storage_key=key
            ).exists():
                continue

            try:
                current_modified = storage.get_modified_time(key)
            except FileNotFoundError:
                continue

            if current_modified > cutoff:
                skipped_recent += 1
                continue

            try:
                storage.delete(key)
            except OSError as exc:
                raise CommandError(
                    f"Could not delete {key}: {exc}"
                ) from exc

            deleted += 1
            self.stdout.write(f"Deleted orphan: {key}")

        # Phase 2: Attachments of old soft-deleted messages.
        attachment_ids = list(
            ChatAttachment.objects.filter(
                message__deleted_at__isnull=False,
                message__deleted_at__lte=cutoff,
            ).values_list("pk", flat=True)
        )

        for attachment_id in attachment_ids:
            if not should_delete:
                attachment = (
                    ChatAttachment.objects
                    .select_related("message")
                    .filter(pk=attachment_id)
                    .first()
                )
                if attachment is not None:
                    deleted_message_attachments += 1
                    self.stdout.write(
                        "Deleted-message attachment: "
                        f"{attachment.storage_key}"
                    )
                continue

            try:
                cleaned = cleanup_deleted_attachment(
                    attachment_id,
                    cutoff=cutoff,
                )
            except OSError as exc:
                raise CommandError(
                    f"Could not clean attachment {attachment_id}: {exc}"
                ) from exc

            if cleaned:
                deleted_message_attachments += 1
                metadata_removed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned={scanned}, "
                f"Orphaned={orphaned}, "
                f"Deleted={deleted}, "
                f"SkippedRecent={skipped_recent}, "
                f"DeletedMessageAttachments="
                f"{deleted_message_attachments}, "
                f"MetadataRemoved={metadata_removed}"
            )
        )
