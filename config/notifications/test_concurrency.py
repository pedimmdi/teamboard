
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase

from notifications.models import Notification
from notifications.services import create_notification


User = get_user_model()


class NotificationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(
            email="concurrent-recipient@example.com",
        )
        self.actor = User.objects.create_user(
            email="concurrent-actor@example.com",
        )

    def test_concurrent_duplicate_creates_one_notification(self):
        key = f"concurrent:{uuid4()}"
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)

                notification, created = create_notification(
                    recipient=self.recipient,
                    actor=self.actor,
                    event_type=Notification.EventType.TASK_ASSIGNED,
                    deduplication_key=key,
                    payload={"message": "Concurrent event"},
                )

                return notification.pk, created
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker)
                for _ in range(2)
            ]
            results = [
                future.result(timeout=30)
                for future in futures
            ]

        self.assertEqual(
            Notification.objects.filter(
                deduplication_key=key,
            ).count(),
            1,
        )

        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(
            sorted(created for _, created in results),
            [False, True],
        )
