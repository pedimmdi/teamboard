
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chats.models import ChatAttachment
from chats.storage import chat_attachment_storage


class Command(BaseCommand):
    help = "Find or delete orphaned private chat attachment files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete eligible orphan files.",
        )
        parser.add_argument(
            "--min-age-hours",
            type=int,
            default=24,
            help="Minimum file age in hours (default: 24).",
        )

    def handle(self, *args, **options):
        min_age_hours = options["min_age_hours"]

        if min_age_hours < 24:
            raise CommandError(
                "Minimum age must be at least 24 hours."
            )

        storage = chat_attachment_storage()
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=min_age_hours
        )

        try:
            directories, filenames = storage.listdir("uploads")
        except FileNotFoundError:
            self.stdout.write(
                self.style.SUCCESS("No attachment files found.")
            )
            return

        if directories:
            raise CommandError(
                "Unexpected nested directories inside uploads."
            )

        scanned = 0
        orphaned = 0
        deleted = 0
        skipped_recent = 0

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

            if options["delete"]:
                # Recheck immediately before deletion.
                if ChatAttachment.objects.filter(
                    storage_key=key
                ).exists():
                    continue

                try:
                    storage.delete(key)
                except OSError as exc:
                    raise CommandError(
                        f"Could not delete {key}: {exc}"
                    ) from exc

                deleted += 1
                self.stdout.write(f"Deleted: {key}")
            else:
                self.stdout.write(f"Orphan: {key}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned={scanned}, "
                f"Orphaned={orphaned}, "
                f"Deleted={deleted}, "
                f"SkippedRecent={skipped_recent}"
            )
        )
