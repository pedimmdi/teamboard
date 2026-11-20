"""Sanitized operational status for the PostgreSQL reminder schedule."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Min
from django.utils import timezone
from tasks.models import TaskReminder


class Command(BaseCommand):
    help = "Show reminder state counts and overdue age without private task/user data."

    def add_arguments(self, parser):
        parser.add_argument("--max-overdue-age", type=int, default=None, help="Exit nonzero when a pending delivery is older than this many seconds.")

    def handle(self, *args, **options):
        now = timezone.now()
        overdue = TaskReminder.objects.filter(status="pending", run_at__lte=now)
        oldest = overdue.aggregate(value=Min("run_at"))["value"]
        age = max(0, int((now-oldest).total_seconds())) if oldest else 0
        self.stdout.write(json.dumps({
            "counts": dict(TaskReminder.objects.values_list("status").annotate(count=Count("pk")).values_list("status", "count")),
            "due_pending": overdue.count(),
            "retry_due": TaskReminder.objects.filter(status="failed", retry_at__lte=now).count(),
            "needs_recalculation": TaskReminder.objects.filter(needs_recalculation=True).count(),
            "oldest_due_seconds": age,
        }))
        limit = options["max_overdue_age"]
        if limit is not None and age > limit:
            raise CommandError("Task reminder delivery is overdue.")
