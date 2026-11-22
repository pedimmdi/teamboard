
from celery import shared_task
from django.conf import settings

from website.services import (
    purge_expired_contact_messages as purge_messages,
)


@shared_task(ignore_result=True)
def purge_expired_contact_messages():
    """
    Periodically remove expired contact submissions.

    Celery Beat schedules this task daily.
    """
    return purge_messages(
        days=settings.WEBSITE_CONTACT_RETENTION_DAYS
    )
