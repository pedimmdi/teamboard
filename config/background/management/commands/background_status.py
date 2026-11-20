"""Safe operational metadata: never print job payloads or credentials."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min
from django.utils import timezone
from background.models import BackgroundJob

class Command(BaseCommand):
    help = "Report sanitized outbox counts and pending age, optionally failing on excessive backlog age."
    def add_arguments(self, parser):
        parser.add_argument("--max-pending-age", type=int, default=0, help="Alert threshold in seconds; zero disables failure status.")
    def handle(self, *args, **options):
        threshold = options["max_pending_age"]
        if threshold < 0:
            raise CommandError("Age threshold must be non-negative.")
        counts = {state: 0 for state in BackgroundJob.State.values}
        counts.update({row["state"]: row["count"] for row in BackgroundJob.objects.values("state").annotate(count=Count("pk"))})
        oldest = BackgroundJob.objects.filter(state="pending").aggregate(oldest=Min("created_at"))["oldest"]
        age = max(0, int((timezone.now() - oldest).total_seconds())) if oldest else 0
        self.stdout.write(json.dumps({"counts": counts, "oldest_pending_seconds": age}))
        if threshold and age > threshold:
            raise CommandError("Pending background work exceeds the configured age threshold.")
