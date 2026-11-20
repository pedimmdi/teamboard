from django.core.management.base import BaseCommand
from background.tasks import recover_pending_jobs

class Command(BaseCommand):
    help = "Republish due outbox work and expire old payloads; safe after a broker outage."
    def handle(self, *args, **options):
        recover_pending_jobs()
        self.stdout.write("Recovery pass finished; any dispatch failures remain pending.")
