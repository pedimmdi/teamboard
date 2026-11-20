from celery import shared_task
from tasks.reminders import scan_due_reminders

@shared_task(ignore_result=True)
def dispatch_due_reminders():
    scan_due_reminders()
