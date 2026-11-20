from datetime import timedelta
from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from .models import BackgroundJob
from .execution import execute_job

class RetryableJobError(Exception):
    pass

@shared_task(autoretry_for=(RetryableJobError,), retry_backoff=30, retry_backoff_max=3600, retry_jitter=True, max_retries=8, ignore_result=True)
def deliver_job(job_id):
    if execute_job(job_id) == "retry":
        raise RetryableJobError("Background I/O failed; see outbox metadata")

@shared_task(ignore_result=True)
def recover_pending_jobs():
    from .services import dispatch
    now = timezone.now()
    BackgroundJob.objects.filter(state="pending", expires_at__lte=now).update(state="failed", payload={}, last_error="Expired")
    # Bounded batches keep Beat recovery cheap. Duplicate deliveries are safe;
    # each worker serializes on the durable row and checks terminal state.
    for job_id in BackgroundJob.objects.filter(state="pending", available_at__lte=now).filter(Q(dispatched_at__isnull=True) | Q(dispatched_at__lt=now - timedelta(seconds=600))).order_by("available_at").values_list("pk", flat=True)[:100]:
        dispatch(job_id)
    BackgroundJob.objects.filter(state__in=["done", "failed"], created_at__lt=now - timedelta(days=7)).delete()
