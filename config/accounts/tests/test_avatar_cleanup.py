from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.avatar_cleanup import lock_avatar_key
from accounts.models import Profile
from accounts.tests.test_avatars import image_file
from background.execution import execute_job
from background.models import BackgroundJob
from background.services import dispatch, enqueue_avatar_file
from background.tasks import recover_pending_jobs
from projects.models import Project
from workspaces.models import Workspace


class AvatarCleanupTestSetup:
    def setUp(self):
        media = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=media))
        self.publish = self.enterContext(patch("background.services.dispatch"))
        self.profile = get_user_model().objects.create_user(email="avatar-cleanup@example.com").profile
        self.profile.avatar = image_file()
        self.profile.save(update_fields=["avatar"])
        self.key = self.profile.avatar.name

    def remove_avatar(self):
        self.profile.avatar = None
        self.profile.save(update_fields=["avatar"])
        return BackgroundJob.objects.get(kind=BackgroundJob.Kind.AVATAR_FILE)


class AvatarCleanupTests(AvatarCleanupTestSetup, TestCase):
    def test_replacement_rolls_back_the_cleanup_job_with_the_avatar_change(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                self.profile.avatar = image_file()
                self.profile.save(update_fields=["avatar"])
                self.assertEqual(
                    BackgroundJob.objects.get(kind=BackgroundJob.Kind.AVATAR_FILE).payload,
                    {"key": self.key},
                )
                self.assertTrue(default_storage.exists(self.key))
                transaction.set_rollback(True)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar.name, self.key)
        self.assertTrue(default_storage.exists(self.key))
        self.assertFalse(BackgroundJob.objects.exists())
        self.publish.assert_not_called()

    def test_broker_and_storage_failures_leave_retryable_work(self):
        with self.captureOnCommitCallbacks(execute=True):
            job = self.remove_avatar()
            self.publish.assert_not_called()
        self.publish.assert_called_once_with(job.pk)
        with patch("background.tasks.deliver_job.delay", side_effect=OSError):
            with self.assertLogs("background.services", level="ERROR"):
                dispatch(job.pk)
        self.assertTrue(default_storage.exists(self.key))
        self.publish.reset_mock()
        recover_pending_jobs()
        self.publish.assert_called_once_with(job.pk)

        with patch.object(default_storage, "delete", side_effect=OSError("storage temporarily unavailable")):
            with self.assertLogs("background.execution", level="WARNING"):
                self.assertEqual(execute_job(job.pk), "retry")
        job.refresh_from_db()
        self.assertEqual(job.state, BackgroundJob.State.PENDING)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.payload, {"key": self.key})
        self.assertTrue(default_storage.exists(self.key))
        BackgroundJob.objects.filter(pk=job.pk).update(available_at=timezone.now())
        self.assertEqual(execute_job(job.pk), "done")
        self.assertEqual(execute_job(job.pk), "done")
        self.assertFalse(default_storage.exists(self.key))

    def test_cleanup_keeps_a_key_referenced_by_any_avatar_model(self):
        workspace = Workspace.objects.create(name="Shared avatar", avatar=self.key)
        job = self.remove_avatar()
        self.assertEqual(execute_job(job.pk), "done")
        self.assertTrue(default_storage.exists(self.key))

        workspace.avatar = None
        workspace.save(update_fields=["avatar"])
        job = BackgroundJob.objects.get(state=BackgroundJob.State.PENDING)
        self.assertEqual(execute_job(job.pk), "done")
        self.assertFalse(default_storage.exists(self.key))

    def test_cascade_uses_latest_stored_avatar_keys(self):
        workspace = Workspace.objects.create(name="Avatar workspace", avatar=image_file())
        project = Project.objects.create(workspace=workspace, name="Avatar project", avatar=image_file())
        stale_workspace = Workspace.objects.get(pk=workspace.pk)
        workspace.avatar = image_file()
        workspace.save(update_fields=["avatar"])
        expected = {stale_workspace.avatar.name, workspace.avatar.name, project.avatar.name}

        stale_workspace.delete()
        jobs = BackgroundJob.objects.filter(kind=BackgroundJob.Kind.AVATAR_FILE)
        self.assertEqual({job.payload["key"] for job in jobs}, expected)
        for job in jobs:
            execute_job(job.pk)
        self.assertFalse(any(default_storage.exists(key) for key in expected))

    def test_recovery_command_queues_only_old_managed_orphans(self):
        old = default_storage.save(f"profile_images/77/{uuid4().hex}.webp", ContentFile(b"old"))
        recent = default_storage.save(f"profile_images/77/{uuid4().hex}.webp", ContentFile(b"recent"))
        unrelated = default_storage.save("profile_images/77/notes.webp", ContentFile(b"unrelated"))
        yesterday = timezone.now() - timedelta(days=2)
        with patch.object(default_storage, "get_modified_time", side_effect=lambda key: timezone.now() if key == recent else yesterday):
            out = StringIO()
            call_command("cleanup_avatar_files", stdout=out)
            self.assertIn("Found 1", out.getvalue())
            self.assertFalse(BackgroundJob.objects.exists())
            call_command("cleanup_avatar_files", "--apply", stdout=StringIO())
            call_command("cleanup_avatar_files", "--apply", stdout=StringIO())
        job = BackgroundJob.objects.get()
        self.assertEqual(job.payload, {"key": old})
        execute_job(job.pk)
        self.assertFalse(default_storage.exists(old))
        for key in (self.key, recent, unrelated):
            self.assertTrue(default_storage.exists(key))


class AvatarCleanupConcurrencyTests(AvatarCleanupTestSetup, TransactionTestCase):
    def test_parallel_replacement_tracks_both_intermediate_files(self):
        start = Barrier(2)

        def replace():
            try:
                profile = Profile.objects.get(pk=self.profile.pk)
                profile.avatar = image_file()
                start.wait(timeout=10)
                profile.save(update_fields=["avatar"])
                return profile.avatar.name
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            replacements = [pool.submit(replace) for _ in range(2)]
            uploaded = {future.result(timeout=15) for future in replacements}

        self.profile.refresh_from_db()
        latest = self.profile.avatar.name
        self.assertIn(latest, uploaded)
        jobs = list(BackgroundJob.objects.filter(kind=BackgroundJob.Kind.AVATAR_FILE))
        self.assertEqual(len(jobs), 2)
        self.assertEqual({job.payload["key"] for job in jobs}, {self.key} | (uploaded - {latest}))
        for job in jobs:
            execute_job(job.pk)
        self.assertTrue(default_storage.exists(latest))

    def test_worker_and_reattachment_cannot_create_a_dangling_reference(self):
        job = self.remove_avatar()
        deletion_started = Event()
        reattachment_started = Event()
        delete = default_storage.delete

        def delayed_delete(key):
            deletion_started.set()
            if not reattachment_started.wait(timeout=10):
                raise RuntimeError("Reattachment did not reach its lock")
            delete(key)

        def worker():
            try:
                return execute_job(job.pk)
            finally:
                connections.close_all()

        def reattach():
            try:
                if not deletion_started.wait(timeout=10):
                    raise RuntimeError("Cleanup worker did not reach storage")
                profile = Profile.objects.get(pk=self.profile.pk)
                profile.avatar = self.key
                profile.save(update_fields=["avatar"])
            finally:
                connections.close_all()

        def lock_during_reattachment(key, using):
            reattachment_started.set()
            lock_avatar_key(key, using)

        with patch.object(default_storage, "delete", side_effect=delayed_delete):
            with patch("accounts.signals.lock_avatar_key", side_effect=lock_during_reattachment):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    cleanup = pool.submit(worker)
                    writer = pool.submit(reattach)
                    self.assertEqual(cleanup.result(timeout=15), "done")
                    with self.assertRaises(ValidationError):
                        writer.result(timeout=15)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.avatar)
        self.assertFalse(default_storage.exists(self.key))
