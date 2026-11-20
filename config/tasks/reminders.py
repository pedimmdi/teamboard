"""Private task reminders; PostgreSQL is the schedule and delivery ledger."""
import logging
from datetime import datetime, timedelta, timezone as utc
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError
from tasks.models import Task, TaskReminder
from tasks.services import _lock_project
from projects.access import get_project_membership_or_404
from notifications.models import Notification
from notifications.services import create_notification

logger = logging.getLogger(__name__)
ACTIVE = ("pending", "disabled", "invalid", "failed")


def relative_time(due_date, zone, days_before, local_time):
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError({"timezone": "Choose a valid IANA timezone."})
    naive = datetime.combine(due_date - timedelta(days=days_before), local_time)
    candidates = set()
    for fold in (0, 1):
        value = naive.replace(tzinfo=tz, fold=fold).astimezone(utc.utc)
        if value.astimezone(tz).replace(tzinfo=None) == naive:
            candidates.add(value)
    if len(candidates) != 1:
        raise ValidationError({"local_time": "This local time is ambiguous or does not exist due to a timezone change. Choose another time or an absolute time with an explicit offset."})
    return candidates.pop()


def reconcile(reminder, task, now):
    if reminder.status not in ACTIVE:
        return
    if task.status == "done":
        reminder.status, reminder.last_error = "cancelled", "TaskCompleted"
    elif reminder.kind == "relative":
        if task.due_date is None:
            reminder.status, reminder.run_at, reminder.last_error = "disabled", None, "NoDueDate"
        else:
            try:
                value = relative_time(task.due_date, reminder.timezone, reminder.days_before, reminder.local_time)
                # Unchanged overdue reminders must still deliver after an outage.
                if reminder.needs_recalculation or reminder.status in ("disabled", "invalid"):
                    reminder.run_at = value
                    reminder.status = "pending" if value > now else "invalid"
                    reminder.last_error = "" if value > now else "RescheduledIntoPast"
                    reminder.retry_at = None
            except ValidationError:
                reminder.status, reminder.last_error = "invalid", "InvalidLocalTime"
    if reminder.status == "pending" and TaskReminder.objects.filter(task=task, recipient_id=reminder.recipient_id, status="pending", run_at=reminder.run_at).exclude(pk=reminder.pk).exists():
        reminder.status, reminder.last_error = "invalid", "DuplicateTime"
    reminder.needs_recalculation = False
    reminder.save()


def sync_task_reminders(task):
    for reminder in TaskReminder.objects.select_for_update().filter(task=task, needs_recalculation=True, status__in=ACTIVE):
        reconcile(reminder, task, timezone.now())


@transaction.atomic
def save_reminder(*, task, actor, data, reminder_id=None):
    _lock_project(project_id=task.project_id)
    task = get_object_or_404(Task.objects.select_for_update(), pk=task.pk)
    get_project_membership_or_404(project_id=task.project_id, user=actor)
    if not actor.is_active:
        raise PermissionDenied("Inactive account.")
    reminder = get_object_or_404(TaskReminder.objects.select_for_update(), pk=reminder_id, task=task, recipient=actor) if reminder_id else TaskReminder(task=task, recipient=actor)
    if reminder_id and reminder.status not in ACTIVE:
        raise ValidationError({"status": "Sent or cancelled reminders cannot be edited. Create a new reminder instead."})
    if task.status == "done":
        raise ValidationError({"task": "Reopen the task before scheduling a reminder."})
    if not reminder_id and TaskReminder.objects.filter(task=task, recipient=actor, status__in=ACTIVE).count() >= 3:
        raise ValidationError({"reminders": "At most three active reminders per task are allowed."})
    for key, value in data.items():
        if key not in {"kind", "timezone", "run_at", "days_before", "local_time"}:
            raise ValidationError({key: "This field cannot be supplied."})
        setattr(reminder, key, value)
    if reminder.kind not in TaskReminder.Kind.values:
        raise ValidationError({"kind": "Choose a valid reminder type."})
    try:
        ZoneInfo(reminder.timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValidationError({"timezone": "Choose a valid IANA timezone."})
    if reminder.kind == "relative":
        if task.due_date is None:
            raise ValidationError({"kind": "Relative reminders require a task due date."})
        if reminder.days_before is None or reminder.local_time is None:
            raise ValidationError({"kind": "Relative reminders require days_before and local_time."})
        if not 0 <= reminder.days_before <= 365 or reminder.local_time.tzinfo is not None:
            raise ValidationError({"kind": "Use zero to 365 days and a local clock time without an offset."})
        reminder.run_at = relative_time(task.due_date, reminder.timezone, reminder.days_before, reminder.local_time)
    else:
        reminder.days_before = reminder.local_time = None
    if reminder.run_at is None or timezone.is_naive(reminder.run_at) or reminder.run_at <= timezone.now():
        raise ValidationError({"run_at": "Choose a future reminder time."})
    duplicate = TaskReminder.objects.filter(task=task, recipient=actor, status__in=ACTIVE, run_at=reminder.run_at).exclude(pk=reminder.pk).exists()
    if duplicate:
        raise ValidationError({"run_at": "You already have a reminder at this time."})
    reminder.status, reminder.last_error = "pending", ""
    reminder.needs_recalculation = False
    reminder.attempts = 0
    reminder.retry_at = None
    reminder.save()
    return reminder


@transaction.atomic
def cancel_reminder(*, task, actor, reminder_id):
    _lock_project(project_id=task.project_id)
    get_project_membership_or_404(project_id=task.project_id, user=actor)
    reminder = get_object_or_404(TaskReminder.objects.select_for_update(), pk=reminder_id, task=task, recipient=actor)
    if reminder.status == "sent":
        return  # Keep the delivery audit; the notification is managed in Inbox.
    reminder.status = "cancelled"
    reminder.needs_recalculation = False
    reminder.retry_at = None
    reminder.save(update_fields=["status", "needs_recalculation", "retry_at", "updated_at"])


@transaction.atomic
def process_reminder(reminder_id):
    pointer = TaskReminder.objects.filter(pk=reminder_id).values("task_id", "task__project_id").first()
    if pointer is None:
        return
    _lock_project(project_id=pointer["task__project_id"])
    task = Task.objects.select_for_update().select_related("project__workspace").filter(pk=pointer["task_id"]).first()
    if task is None:
        return
    reminder = TaskReminder.objects.select_for_update().select_related("recipient").filter(pk=reminder_id).first()
    if reminder is None or reminder.status not in ACTIVE:
        return
    now = timezone.now()
    reconcile(reminder, task, now)
    user = type(reminder.recipient).objects.select_for_update().get(pk=reminder.recipient_id)
    try:
        if not user.is_active:
            raise PermissionDenied()
        get_project_membership_or_404(project_id=task.project_id, user=user)
    except (Http404, PermissionDenied):
        reminder.status, reminder.last_error = "cancelled", "AccessRevoked"
        reminder.save()
        return
    if reminder.status not in ("pending", "failed") or not reminder.run_at or reminder.run_at > now or (reminder.retry_at and reminder.retry_at > now):
        return
    notification, _ = create_notification(recipient=user, actor=None, event_type=Notification.EventType.TASK_REMINDER,
        workspace=task.project.workspace, project=task.project, task=task,
        payload={"reminder_id": str(reminder.pk)}, deduplication_key=f"task_reminder:{reminder.pk}")
    reminder.status, reminder.sent_at, reminder.notification = "sent", now, notification
    reminder.attempts += 1
    reminder.last_error = ""
    reminder.retry_at = None
    reminder.save()
    logger.info("Task reminder delivered reminder=%s", reminder.pk)


def scan_due_reminders(batch_size=100):
    from django.db.models import Q
    now = timezone.now()
    candidates = TaskReminder.objects.filter(
        Q(needs_recalculation=True, status__in=ACTIVE) | Q(status="pending", run_at__lte=now) | Q(status="failed", retry_at__lte=now)
    ).order_by("run_at", "id").values_list("pk", flat=True)[:batch_size]
    for reminder_id in list(candidates):
        try:
            process_reminder(reminder_id)
        except Http404:
            # Parent project/task deletion raced the initial pointer lookup.
            continue
        except Exception as exc:
            logger.error("Task reminder processing failed reminder=%s error=%s", reminder_id, type(exc).__name__)
            # Re-lock using the same parent-first order: never overwrite a
            # delivery/cancellation committed by another worker after rollback.
            pointer = TaskReminder.objects.filter(pk=reminder_id).values("task__project_id").first()
            if pointer:
                try:
                    with transaction.atomic():
                        _lock_project(project_id=pointer["task__project_id"])
                        reminder = TaskReminder.objects.select_for_update().filter(pk=reminder_id, status__in=("pending", "failed")).first()
                        if reminder:
                            reminder.attempts += 1
                            reminder.status = "failed"
                            reminder.last_error = type(exc).__name__[:100]
                            reminder.retry_at = timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(reminder.attempts, 6)))
                            reminder.save()
                except Http404:
                    continue
