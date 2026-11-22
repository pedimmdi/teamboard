from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, time, timedelta, timezone as utc
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections, transaction, IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from notifications.models import Notification
from tasks.models import Task, TaskReminder
from tasks.reminders import save_reminder, process_reminder, scan_due_reminders, relative_time
from tasks.services import update_task
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()

class ReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.admin, cls.member, cls.other, cls.outsider = [User.objects.create_user(email=f"reminder-{name}@example.com") for name in ("owner","admin","member","other","outside")]
        cls.workspace = Workspace.objects.create(name="Reminders")
        for user, role in ((cls.owner,"owner"),(cls.admin,"admin"),(cls.member,"member"),(cls.other,"member")):
            WorkspaceMembership.objects.create(workspace=cls.workspace,user=user,role=role)
        cls.project = Project.objects.create(workspace=cls.workspace,name="Private",created_by=cls.owner)
        for user, role in ((cls.owner,"manager"),(cls.member,"member"),(cls.other,"member")):
            ProjectMembership.objects.create(project=cls.project,user=user,role=role)
        cls.task = Task.objects.create(project=cls.project,assignee=cls.owner,title="A reminder task",due_date=date(2030,5,20))
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.member)
        self.url=f"/api/v1/workspaces/{self.workspace.slug}/projects/{self.project.pk}/tasks/{self.task.pk}/reminders/"
    def payload(self, **extra):
        return {"kind":"absolute","timezone":"Asia/Tehran","run_at":(timezone.now()+timedelta(days=2)).isoformat(),**extra}
    def create(self, user=None, **extra):
        data=self.payload(**extra)
        data["run_at"]=datetime.fromisoformat(data["run_at"])
        return save_reminder(task=self.task,actor=user or self.member,data=data)
    def due(self, user=None):
        reminder=self.create(user)
        TaskReminder.objects.filter(pk=reminder.pk).update(run_at=timezone.now()-timedelta(minutes=2))
        reminder.refresh_from_db();return reminder
    def test_crud_is_private_and_cancellation_releases_active_slot(self):
        response=self.client.post(self.url,self.payload(),format="json")
        self.assertEqual(response.status_code,201,response.data)
        reminder_id=response.data["id"]
        self.assertEqual(self.client.get(self.url).data["count"],1)
        changed=self.client.patch(self.url+reminder_id+"/",{"run_at":(timezone.now()+timedelta(days=3)).isoformat()},format="json")
        self.assertEqual(changed.status_code,200,changed.data)
        self.assertEqual(self.client.delete(self.url+reminder_id+"/").status_code,204)
        self.assertEqual(TaskReminder.objects.get(pk=reminder_id).status,"cancelled")
    def test_foreign_reminders_and_recipient_spoof_are_rejected(self):
        reminder=self.create(self.other)
        self.assertEqual(self.client.get(self.url).data["count"],0)
        self.assertEqual(self.client.patch(self.url+str(reminder.pk)+"/",self.payload(),format="json").status_code,404)
        self.assertEqual(self.client.delete(self.url+str(reminder.pk)+"/").status_code,404)
        for key in ("user_id","recipient","recipient_id","status","task"):
            self.assertEqual(self.client.post(self.url,self.payload(**{key:self.other.pk}),format="json").status_code,400)
    def test_roles_and_outsiders(self):
        for user in (self.owner,self.admin,self.member):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.url,self.payload(),format="json").status_code,201)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code,401)
    def test_limit_three_and_duplicates(self):
        for day in range(1,4):
            self.assertEqual(self.client.post(self.url,self.payload(run_at=(timezone.now()+timedelta(days=day)).isoformat()),format="json").status_code,201)
        self.assertEqual(self.client.post(self.url,self.payload(),format="json").status_code,400)
        self.client.force_authenticate(self.other)
        fixed=self.payload(run_at="2030-01-01T00:00:00Z")
        self.assertEqual(self.client.post(self.url,fixed,format="json").status_code,201)
        self.assertEqual(self.client.post(self.url,fixed,format="json").status_code,400)
    def test_invalid_past_naive_zone_and_relative_inputs(self):
        for payload in ([{}], "invalid", 7):
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 400)
        for payload in (self.payload(run_at="2020-01-01T00:00:00Z"),self.payload(run_at="2030-01-01T00:00:00"),self.payload(timezone="Invalid/Zone"),{"kind":"relative","timezone":"UTC","days_before":366},self.payload(days_before=1)):
            self.assertEqual(self.client.post(self.url,payload,format="json").status_code,400,payload)
    def test_relative_defaults_and_due_date_change(self):
        response=self.client.post(self.url,{"kind":"relative","timezone":"Asia/Tehran","days_before":1},format="json")
        self.assertEqual(response.status_code,201,response.data)
        reminder=TaskReminder.objects.get(pk=response.data["id"])
        self.assertEqual(reminder.run_at,datetime(2030,5,19,5,30,tzinfo=utc.utc))
        update_task(task=self.task,actor=self.owner,due_date=date(2030,5,22),update_due_date=True)
        reminder.refresh_from_db()
        self.assertEqual(reminder.run_at,datetime(2030,5,21,5,30,tzinfo=utc.utc))
    def test_removed_due_date_disables_and_reintroduced_date_reactivates(self):
        self.client.post(self.url,{"kind":"relative","timezone":"UTC"},format="json")
        Task.objects.filter(pk=self.task.pk).update(due_date=None)
        response=self.client.get(self.url)
        self.assertEqual(response.data["results"][0]["status"],"disabled")
        Task.objects.filter(pk=self.task.pk).update(due_date=date(2030,6,1))
        scan_due_reminders()
        self.assertEqual(TaskReminder.objects.get().status,"pending")
    def test_bulk_due_change_to_past_invalidates_without_delivery(self):
        self.client.post(self.url,{"kind":"relative","timezone":"UTC"},format="json")
        Task.objects.filter(pk=self.task.pk).update(due_date=date(2020,1,1))
        scan_due_reminders()
        self.assertEqual(TaskReminder.objects.get().status,"invalid")
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())
    def test_absolute_reminder_without_due_date(self):
        Task.objects.filter(pk=self.task.pk).update(due_date=None)
        self.assertEqual(self.client.post(self.url,self.payload(),format="json").status_code,201)
        self.assertEqual(self.client.post(self.url,{"kind":"relative"},format="json").status_code,400)
    def test_timezone_dst_gap_fold_and_conversion(self):
        for day in (date(2030,3,31),date(2030,10,27)):
            with self.assertRaises(ValidationError):relative_time(day,"Europe/Paris",0,time(2,30))
        self.assertEqual(relative_time(date(2030,6,1),"America/New_York",0,time(9)),datetime(2030,6,1,13,tzinfo=utc.utc))
    def test_future_does_not_deliver_and_late_delivery_is_once(self):
        reminder=self.create()
        process_reminder(reminder.pk)
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())
        TaskReminder.objects.filter(pk=reminder.pk).update(run_at=timezone.now()-timedelta(days=1))
        scan_due_reminders();scan_due_reminders()
        reminder.refresh_from_db()
        self.assertEqual(reminder.status,"sent")
        self.assertEqual(Notification.objects.filter(deduplication_key=f"task_reminder:{reminder.pk}").count(),1)
        inbox=self.client.get("/api/v1/notifications/")
        self.assertEqual(inbox.status_code,200)
        self.assertTrue(any(row["event_type"]=="task_reminder" for row in inbox.data["results"]))
    def test_membership_and_account_revocation_cancel(self):
        reminder=self.due()
        ProjectMembership.objects.filter(project=self.project,user=self.member).delete()
        process_reminder(reminder.pk)
        reminder.refresh_from_db();self.assertEqual(reminder.status,"cancelled")
        inactive=self.due(self.other)
        User.objects.filter(pk=self.other.pk).update(is_active=False)
        process_reminder(inactive.pk)
        inactive.refresh_from_db();self.assertEqual(inactive.status,"cancelled")
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())
    def test_assignee_change_does_not_cancel_an_authorized_users_reminder(self):
        reminder=self.due()
        update_task(task=self.task,actor=self.owner,assignee=self.other,update_assignee=True)
        process_reminder(reminder.pk)
        reminder.refresh_from_db();self.assertEqual(reminder.status,"sent")
    def test_task_completion_deletion_and_cancel_are_safe(self):
        reminder=self.due()
        Task.objects.filter(pk=self.task.pk).update(status="done")
        process_reminder(reminder.pk)
        reminder.refresh_from_db();self.assertEqual(reminder.status,"cancelled")
        self.task.delete()
        process_reminder(reminder.pk)
        self.assertFalse(TaskReminder.objects.filter(pk=reminder.pk).exists())
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())
    def test_rollback_and_failure_recovery_are_atomic(self):
        reminder=self.due()
        original=TaskReminder.save
        def fail_after_notification(instance,*args,**kwargs):
            if instance.status=="sent":raise OSError("Temporary DB boundary failure")
            return original(instance,*args,**kwargs)
        with patch.object(TaskReminder,"save",autospec=True,side_effect=fail_after_notification):
            scan_due_reminders()
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())
        reminder.refresh_from_db();self.assertEqual(reminder.status,"failed")
        TaskReminder.objects.filter(pk=reminder.pk).update(retry_at=timezone.now()-timedelta(seconds=1))
        scan_due_reminders();scan_due_reminders()
        self.assertEqual(Notification.objects.filter(event_type="task_reminder").count(),1)
    def test_reminder_create_rollback_has_no_schedule_or_notification(self):
        with transaction.atomic():
            reminder=self.create()
            transaction.set_rollback(True)
        self.assertFalse(TaskReminder.objects.filter(pk=reminder.pk).exists())
    def test_scan_respects_batch_bound(self):
        for user in (self.member,self.other,self.owner):self.due(user)
        scan_due_reminders(batch_size=1)
        self.assertEqual(Notification.objects.filter(event_type="task_reminder").count(),1)

    def test_workspace_access_revocation_and_admin_downgrade(self):
        member_reminder = self.due()
        WorkspaceMembership.objects.filter(workspace=self.workspace, user=self.member).delete()
        process_reminder(member_reminder.pk)
        member_reminder.refresh_from_db()
        self.assertEqual(member_reminder.last_error, "AccessRevoked")
        admin_reminder = self.due(self.admin)
        WorkspaceMembership.objects.filter(workspace=self.workspace, user=self.admin).update(role="member")
        process_reminder(admin_reminder.pk)
        admin_reminder.refresh_from_db()
        self.assertEqual(admin_reminder.last_error, "AccessRevoked")
        self.assertFalse(Notification.objects.filter(event_type="task_reminder").exists())

    def test_foreign_task_scope_and_sent_audit(self):
        reminder = self.due()
        wrong_project = Project.objects.create(workspace=self.workspace, name="Other", created_by=self.owner)
        ProjectMembership.objects.create(project=wrong_project, user=self.owner, role="manager")
        self.assertEqual(self.client.get(self.url.replace(str(self.project.pk), str(wrong_project.pk))).status_code, 404)
        process_reminder(reminder.pk)
        self.assertEqual(self.client.patch(self.url+str(reminder.pk)+"/", self.payload(), format="json").status_code, 400)
        self.assertEqual(self.client.delete(self.url+str(reminder.pk)+"/").status_code, 204)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "sent")
        self.assertIsNotNone(reminder.notification_id)

    def test_database_duplicate_constraint_and_service_validation(self):
        reminder = self.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskReminder.objects.create(task=self.task, recipient=self.member, kind="absolute", run_at=reminder.run_at)
        for changes in ({"timezone":"Invalid/Zone"}, {"kind":"invalid"}, {"recipient":self.other}, {"run_at":datetime(2030,1,1)}):
            with self.assertRaises(ValidationError):
                save_reminder(task=self.task, actor=self.member, data={"kind":"absolute", "timezone":"UTC", "run_at":timezone.now()+timedelta(days=4), **changes})

    def test_read_and_write_throttles_are_separate(self):
        from rest_framework.throttling import ScopedRateThrottle
        from django.core.cache import cache
        cache.clear()
        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"reminder_read":"1/min", "reminder_write":"1/min"}):
            self.assertEqual(self.client.get(self.url).status_code, 200)
            self.assertEqual(self.client.get(self.url).status_code, 429)
            self.assertEqual(self.client.post(self.url, self.payload(), format="json").status_code, 201)
            self.assertEqual(self.client.post(self.url, self.payload(), format="json").status_code, 429)
        cache.clear()

    def test_monitoring_exposes_only_counts_and_overdue_age(self):
        from django.core.management import call_command, CommandError
        from io import StringIO
        import json
        self.due()
        output = StringIO()
        call_command("reminder_status", stdout=output)
        data = json.loads(output.getvalue())
        self.assertEqual(data["counts"]["pending"], 1)
        self.assertEqual(data["due_pending"], 1)
        self.assertGreater(data["oldest_due_seconds"], 60)
        self.assertNotIn(self.member.email, output.getvalue())
        self.assertNotIn(self.task.title, output.getvalue())
        with self.assertRaises(CommandError):
            call_command("reminder_status", max_overdue_age=60, stdout=StringIO())

class ReminderConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner=User.objects.create_user(email="reminder-race@example.com")
        self.workspace=Workspace.objects.create(name="Reminder race")
        WorkspaceMembership.objects.create(workspace=self.workspace,user=self.owner,role="owner")
        with transaction.atomic():
            self.project=Project.objects.create(workspace=self.workspace,name="Race",created_by=self.owner)
            ProjectMembership.objects.create(project=self.project,user=self.owner,role="manager")
        self.task=Task.objects.create(project=self.project,assignee=self.owner,title="Race")
    def test_two_workers_create_exactly_one_notification(self):
        reminder=save_reminder(task=self.task,actor=self.owner,data={"kind":"absolute","timezone":"UTC","run_at":timezone.now()+timedelta(days=1)})
        TaskReminder.objects.filter(pk=reminder.pk).update(run_at=timezone.now()-timedelta(minutes=1))
        barrier=Barrier(2)
        def worker(_):
            try:barrier.wait(timeout=10);process_reminder(reminder.pk)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,range(2)))
        self.assertEqual(Notification.objects.filter(deduplication_key=f"task_reminder:{reminder.pk}").count(),1)
        reminder.refresh_from_db();self.assertEqual(reminder.status,"sent")
    def test_concurrent_creations_respect_active_limit(self):
        barrier=Barrier(4)
        def worker(index):
            try:
                barrier.wait(timeout=10)
                try:
                    save_reminder(task=self.task,actor=self.owner,data={"kind":"absolute","timezone":"UTC","run_at":datetime(2030,1,index+1,tzinfo=utc.utc)})
                    return True
                except ValidationError:return False
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(worker,range(4)))
        self.assertEqual(sum(result),3)

    def test_migration_preserves_rows_and_due_trigger_rolls_back_atomically(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        reminder = save_reminder(task=self.task, actor=self.owner, data={"kind":"absolute", "timezone":"UTC", "run_at":timezone.now()+timedelta(days=3)})
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("tasks", "0008_taskreminder")])
            self.assertTrue(TaskReminder.objects.filter(pk=reminder.pk).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
        Task.objects.filter(pk=self.task.pk).update(due_date=date(2030,6,1))
        TaskReminder.objects.filter(pk=reminder.pk).update(kind="relative", days_before=1, local_time=time(9))
        with transaction.atomic():
            Task.objects.filter(pk=self.task.pk).update(due_date=None)
            self.assertTrue(TaskReminder.objects.get(pk=reminder.pk).needs_recalculation)
            transaction.set_rollback(True)
        reminder.refresh_from_db()
        self.assertFalse(reminder.needs_recalculation)
        Task.objects.filter(pk=self.task.pk).update(due_date=None)
        scan_due_reminders()
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "disabled")
