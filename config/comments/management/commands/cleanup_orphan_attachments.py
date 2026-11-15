
import logging
import re
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from comments.models import CommentAttachment
from comments.storage import attachment_storage


logger = logging.getLogger(__name__)

UPLOAD_NAME_PATTERN = re.compile(
    r"^[0-9a-f]{32}(?:_[A-Za-z0-9]+)?$"
)


class Command(BaseCommand):
    help = (
        "Find and optionally delete orphan comment attachments "
        "older than the configured grace period."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
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

        storage = attachment_storage()

        if not hasattr(storage, "path"):
            raise CommandError(
                "This command requires filesystem storage."
            )

        uploads_dir = Path(storage.path("uploads"))

        if not uploads_dir.exists():
            self.stdout.write("No uploads directory found.")
            return

        if uploads_dir.is_symlink() or not uploads_dir.is_dir():
            raise CommandError(
                "Uploads path must be a real directory."
            )

        cutoff = timezone.now() - timedelta(
            hours=min_age_hours
        )

        checked = 0
        orphaned = 0
        deleted = 0
        errors = 0

        for path in uploads_dir.iterdir():
            if path.is_symlink() or not path.is_file():
                continue

            if not UPLOAD_NAME_PATTERN.fullmatch(path.name):
                continue

            checked += 1

            try:
                modified_at = timezone.datetime.fromtimestamp(
                    path.stat().st_mtime,
                    tz=timezone.get_current_timezone(),
                )

                if modified_at > cutoff:
                    continue

                storage_key = f"uploads/{path.name}"

                if CommentAttachment.objects.filter(
                    storage_key=storage_key
                ).exists():
                    continue

                orphaned += 1

                if not options["execute"]:
                    self.stdout.write(
                        f"ORPHAN: {storage_key}"
                    )
                    continue

                # Recheck immediately before deletion.
                if CommentAttachment.objects.filter(
                    storage_key=storage_key
                ).exists():
                    continue

                storage.delete(storage_key)
                deleted += 1

                self.stdout.write(
                    f"DELETED: {storage_key}"
                )

            except Exception:
                errors += 1
                logger.exception(
                    "Attachment cleanup failed for %s",
                    path.name,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked={checked}, "
                f"Orphans={orphaned}, "
                f"Deleted={deleted}, "
                f"Errors={errors}"
            )
        )

        if errors:
            raise CommandError(
                f"Cleanup finished with {errors} errors."
            )
