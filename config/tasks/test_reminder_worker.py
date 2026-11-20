"""Real Redis publication and separate-worker recovery for database schedules."""
import os
import subprocess
import sys
import time
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from kombu.exceptions import OperationalError

from background.test_delivery import real_delivery
from config.celery import app
from notifications.models import Notification
from projects.models import Project, ProjectMembership
from tasks.models import Task, TaskReminder
from tasks.reminder_jobs import dispatch_due_reminders
from tasks.reminders import save_reminder
from workspaces.models import Workspace, WorkspaceMembership


class ReminderWorkerTests(TransactionTestCase):
    def test_broker_failure_worker_restart_and_duplicate_dispatch_recover_once(self):
        if os.environ.get("RUN_REDIS_TESTS") != "1":
            self.skipTest("Requires real Redis")
        owner = get_user_model().objects.create_user(email="reminder-worker@example.com")
        workspace = Workspace.objects.create(name="Reminder worker")
        WorkspaceMembership.objects.create(workspace=workspace, user=owner, role="owner")
        with transaction.atomic():
            project = Project.objects.create(workspace=workspace, name="Worker", created_by=owner)
            ProjectMembership.objects.create(project=project, user=owner, role="manager")
        task = Task.objects.create(project=project, assignee=owner, title="Worker reminder")
        reminder = save_reminder(task=task, actor=owner, data={"kind":"absolute", "timezone":"UTC", "run_at":timezone.now()+timedelta(days=1)})
        TaskReminder.objects.filter(pk=reminder.pk).update(run_at=timezone.now()-timedelta(minutes=5))
        queue, hostname = "reminder."+uuid4().hex, "reminder-"+uuid4().hex+"@test"
        worker = None

        def start_worker():
            child = subprocess.Popen([
                sys.executable, "-m", "celery", "-A", "config", "worker", "--pool=solo", "--concurrency=1",
                "--queues="+queue, "--hostname="+hostname, "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=WARNING",
            ], cwd=settings.BASE_DIR, env={**os.environ, "POSTGRES_DB":connection.settings_dict["NAME"], "CELERY_TASK_ALWAYS_EAGER":"False"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic()+30
            while time.monotonic()<deadline and child.poll() is None:
                if app.control.ping(destination=[hostname], timeout=1):
                    return child
            child.terminate()
            child.wait(timeout=15)
            self.fail("Reminder worker did not become ready")

        def stop_worker(child):
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)

        try:
            with real_delivery():
                # Broker outages affect dispatch, never the PostgreSQL schedule.
                with patch.object(app.amqp, "send_task_message", side_effect=OperationalError("Broker unavailable")):
                    with self.assertRaises(OperationalError):
                        dispatch_due_reminders.apply_async(queue=queue, retry=False)
                reminder.refresh_from_db()
                self.assertEqual(reminder.status, "pending")
                worker = start_worker()
                stop_worker(worker)
                worker = None
                # Beat can dispatch while the worker is down. Restart consumes it.
                dispatch_due_reminders.apply_async(queue=queue)
                dispatch_due_reminders.apply_async(queue=queue)
                worker = start_worker()
                deadline = time.monotonic()+25
                delivered = 0
                while time.monotonic()<deadline:
                    stats = app.control.inspect(destination=[hostname], timeout=1).stats() or {}
                    delivered = stats.get(hostname, {}).get("total", {}).get("tasks.reminder_jobs.dispatch_due_reminders", 0)
                    if delivered >= 2:
                        break
                    time.sleep(.1)
                self.assertGreaterEqual(delivered, 2)
                reminder.refresh_from_db()
                self.assertEqual(reminder.status, "sent")
                self.assertEqual(Notification.objects.filter(deduplication_key=f"task_reminder:{reminder.pk}").count(), 1)
                self.assertEqual(reminder.attempts, 1)
        finally:
            if worker is not None:
                stop_worker(worker)
            with app.connection_for_write() as broker:
                broker.default_channel.queue_delete(queue)
