from datetime import timedelta
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from comments.models import CommentAttachment
from comments.storage import attachment_storage


class Command(BaseCommand):
    help = "Report unreferenced comment files older than a day. Pause comment writes and migrations before using --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        storage = attachment_storage()
        cutoff = timezone.now() - timedelta(days=1)
        failures = 0
        for directory in ("uploads", "legacy"):
            try:
                _, files = storage.listdir(directory)
            except FileNotFoundError:
                continue
            for name in files:
                try:
                    if UUID(hex=name).hex != name:
                        continue
                except ValueError:
                    continue
                key = f"{directory}/{name}"
                try:
                    if storage.get_modified_time(key) >= cutoff:
                        continue
                    if CommentAttachment.objects.filter(storage_key=key).exists():
                        continue
                    if options["apply"]:
                        storage.delete(key)
                    self.stdout.write(f"{'Deleted' if options['apply'] else 'Unreferenced'}: {key}")
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    failures += 1
                    self.stderr.write(f"{key}: {exc}")
        if failures:
            raise CommandError(f"{failures} files could not be processed. Run the command again to retry.")
