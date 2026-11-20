"""Real broker + separate worker process. No external SMTP service is used."""
import os
from contextlib import contextmanager
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from background.execution import execute_job
from background.models import BackgroundJob
from background.services import enqueue_email, enqueue_comment_file
from background.tasks import deliver_job
from config.celery import app


@contextmanager
def real_delivery():
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = False
    try:
        yield
    finally:
        app.conf.task_always_eager = previous


class OutboxConcurrencyTests(TransactionTestCase):
    def test_duplicate_workers_serialize_one_side_effect(self):
        with patch("background.services.dispatch"):
            job = enqueue_email("Test", "Body", "sender@example.com", ["recipient@example.com"])
        start = Barrier(2)
        def run(_):
            try:
                start.wait(timeout=10)
                return execute_job(job.pk)
            finally:
                connections.close_all()
        with patch("background.execution.perform") as effect:
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(run, range(2))), ["done", "done"])
            effect.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)


class RealWorkerDeliveryTests(TransactionTestCase):
    def test_real_redis_worker_delivers_after_commit_and_ignores_duplicates(self):
        if os.environ.get("RUN_REDIS_TESTS") != "1":
            self.skipTest("Requires real Redis")
        queue = "integration." + uuid4().hex
        hostname = "integration-" + uuid4().hex + "@test"
        with TemporaryDirectory() as temp:
            mail_path = Path(temp) / "mail"
            attachment_path = Path(temp) / "attachments"
            child_env = {
                **os.environ, "POSTGRES_DB": connection.settings_dict["NAME"],
                "CELERY_TASK_ALWAYS_EAGER": "False",
                "EMAIL_BACKEND": "django.core.mail.backends.filebased.EmailBackend",
                "EMAIL_FILE_PATH": str(mail_path), "COMMENT_ATTACHMENT_ROOT": str(attachment_path),
                "C_FORCE_ROOT": "1",  # isolated test container only
            }
            worker = subprocess.Popen([
                sys.executable, "-m", "celery", "-A", "config", "worker", "--pool=solo", "--concurrency=1",
                "--queues=" + queue, "--hostname=" + hostname, "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=WARNING",
            ], cwd=settings.BASE_DIR, env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 30
                ready = False
                while time.monotonic() < deadline and worker.poll() is None:
                    if app.control.ping(destination=[hostname], timeout=1):
                        ready = True
                        break
                self.assertTrue(ready, "Separate Celery worker did not become ready")
                with override_settings(COMMENT_ATTACHMENT_ROOT=str(attachment_path)), patch("background.services.dispatch"), real_delivery():
                    from comments.storage import attachment_storage
                    storage = attachment_storage()
                    key = storage.save("uploads/" + uuid4().hex, ContentFile(b"private attachment"))
                    with transaction.atomic():
                        mail_job = enqueue_email("Integration mail", "Private body", "sender@example.com", ["recipient@example.com"])
                        cleanup_job = enqueue_comment_file(key)
                        transaction.on_commit(lambda: deliver_job.apply_async(args=[str(mail_job.pk)], queue=queue))
                        transaction.on_commit(lambda: deliver_job.apply_async(args=[str(cleanup_job.pk)], queue=queue))
                        self.assertFalse(mail_path.exists())
                        self.assertTrue(storage.exists(key))
                    deadline = time.monotonic() + 25
                    while time.monotonic() < deadline:
                        if BackgroundJob.objects.filter(pk__in=[mail_job.pk, cleanup_job.pk], state="done").count() == 2:
                            break
                        time.sleep(0.1)
                    self.assertEqual(BackgroundJob.objects.filter(pk__in=[mail_job.pk, cleanup_job.pk], state="done").count(), 2)
                    self.assertFalse(storage.exists(key))
                    self.assertEqual(len(list(mail_path.iterdir())), 1)
                    deliver_job.apply_async(args=[str(mail_job.pk)], queue=queue)
                    deliver_job.apply_async(args=[str(cleanup_job.pk)], queue=queue)
                    deadline = time.monotonic() + 15
                    delivered = 0
                    while time.monotonic() < deadline:
                        stats = app.control.inspect(destination=[hostname], timeout=1).stats() or {}
                        delivered = stats.get(hostname, {}).get("total", {}).get("background.tasks.deliver_job", 0)
                        if delivered >= 4:
                            break
                        time.sleep(0.1)
                    self.assertGreaterEqual(delivered, 4)
                    self.assertEqual(len(list(mail_path.iterdir())), 1)
                    self.assertEqual(list(BackgroundJob.objects.filter(pk__in=[mail_job.pk, cleanup_job.pk]).values_list("attempts", flat=True)), [1, 1])
            finally:
                worker.terminate()
                try:
                    worker.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
                with app.connection_for_write() as broker:
                    broker.default_channel.queue_delete(queue)
