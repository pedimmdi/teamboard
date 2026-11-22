
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from website.services import (
    get_expired_contact_messages,
    purge_expired_contact_messages,
)


class Command(BaseCommand):
    help = (
        "Remove expired public contact messages. "
        "Dry-run by default; use --execute to delete."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=settings.WEBSITE_CONTACT_RETENTION_DAYS,
            help="Contact message retention period in days.",
        )

        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually delete expired messages.",
        )

    def handle(self, *args, **options):
        days = options["days"]

        if not 1 <= days <= 3650:
            raise CommandError(
                "--days must be between 1 and 3650."
            )

        if not options["execute"]:
            count = get_expired_contact_messages(
                days=days
            ).count()

            self.stdout.write(
                f"DRY RUN: {count} contact message(s) "
                f"older than {days} day(s) would be deleted. "
                "Use --execute to confirm."
            )
            return

        deleted = purge_expired_contact_messages(
            days=days
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} contact message(s) "
                f"older than {days} day(s)."
            )
        )
