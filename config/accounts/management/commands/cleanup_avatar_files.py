import re
from datetime import timedelta

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.avatar_cleanup import AVATAR_MODELS, AVATAR_PREFIXES
from background.models import BackgroundJob
from background.services import enqueue_avatar_file


OWNER_ID = re.compile(r"[0-9]+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
AVATAR_FILENAME = re.compile(r"[0-9a-f]{32}(?:_[A-Za-z0-9]{7})?\.(?:jpe?g|png|webp)")


def storage_directories(path):
    try:
        return default_storage.listdir(path)[0]
    except FileNotFoundError:
        return []


def orphaned_keys(cutoff):
    referenced = {
        key
        for label in AVATAR_MODELS
        for key in (
            apps.get_model(label)._base_manager.exclude(avatar__isnull=True)
            .exclude(avatar="").values_list("avatar", flat=True).iterator()
        )
    }
    for prefix in AVATAR_PREFIXES:
        for owner in storage_directories(prefix):
            if not OWNER_ID.fullmatch(owner):
                continue
            path = f"{prefix}/{owner}"
            try:
                _, files = default_storage.listdir(path)
            except FileNotFoundError:
                continue
            for name in files:
                key = f"{path}/{name}"
                if key in referenced or not AVATAR_FILENAME.fullmatch(name):
                    continue
                try:
                    modified = default_storage.get_modified_time(key)
                except FileNotFoundError:
                    continue
                if modified < cutoff:
                    yield key


class Command(BaseCommand):
    help = "Find old unreferenced avatar uploads. Use --apply to enqueue guarded deletion."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--minimum-age-hours", type=int, default=24)

    def handle(self, *args, **options):
        age = options["minimum_age_hours"]
        if age < 24:
            raise CommandError("--minimum-age-hours must be at least 24.")
        cutoff = timezone.now() - timedelta(hours=age)
        count = 0
        pending = BackgroundJob.objects.filter(kind=BackgroundJob.Kind.AVATAR_FILE, state=BackgroundJob.State.PENDING)
        for key in orphaned_keys(cutoff):
            if pending.filter(payload__key=key).exists():
                continue
            if options["apply"]:
                enqueue_avatar_file(key)
            count += 1
        self.stdout.write(f"{'Queued' if options['apply'] else 'Found'} {count} avatar cleanup job(s).")
