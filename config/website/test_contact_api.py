
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.test import override_settings

from rest_framework import status
from rest_framework.test import APITestCase

from website.models import ContactMessage


class WebsiteContactAPITests(APITestCase):

    @override_settings(CORS_ALLOWED_ORIGINS=["https://public.example"])
    def test_browser_can_read_retry_after_header(self):
        response = self.client.post(
            self.url, self.payload, format="json", HTTP_ORIGIN="https://public.example",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("Retry-After", response["Access-Control-Expose-Headers"])

    def setUp(self):
        cache.clear()

        self.url = reverse(
            "website_api_v1:contact_submit"
        )

        self.payload = {
            "name": "Alex Johnson",
            "email": "ALEX@Example.COM",
            "subject": "Question about Teamboard",
            "message": "I would like to know more.",
        }

    def test_anonymous_visitor_can_submit_contact(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            1,
        )

        message = ContactMessage.objects.get()

        self.assertEqual(message.name, "Alex Johnson")
        self.assertEqual(
            message.email,
            "alex@example.com",
        )
        self.assertEqual(
            message.status,
            ContactMessage.Status.NEW,
        )

        self.assertEqual(
            response.data,
            {"detail": "Your message has been received."},
        )

        self.assertNotIn("id", response.data)
        self.assertNotIn("email", response.data)
        self.assertNotIn("message", response.data)

    def test_invalid_fields_are_rejected(self):
        invalid_cases = (
            ("email", "not-an-email"),
            ("name", "  "),
            ("subject", ""),
            ("message", "  "),
        )

        for field, value in invalid_cases:
            with self.subTest(field=field):
                payload = {
                    **self.payload,
                    field: value,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

                self.assertIn(
                    field,
                    response.data,
                )

        self.assertEqual(
            ContactMessage.objects.count(),
            0,
        )

    def test_field_length_limits_are_enforced(self):
        limits = {
            "name": 120,
            "email": 254,
            "subject": 180,
            "message": 5000,
        }

        for field, limit in limits.items():
            with self.subTest(field=field):
                if field == "email":
                    value = (
                        "a" * 245 + "@example.com"
                    )
                else:
                    value = "x" * (limit + 1)

                payload = {
                    **self.payload,
                    field: value,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

        self.assertEqual(
            ContactMessage.objects.count(),
            0,
        )

    def test_contact_endpoint_is_write_only(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        response = self.client.delete(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            0,
        )

    def test_only_json_requests_are_accepted(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            0,
        )

    def test_contact_submission_is_throttled(self):
        with patch(
            "rest_framework.throttling."
            "ScopedRateThrottle.THROTTLE_RATES",
            {"website_contact": "2/hour"},
        ):
            first = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

            second = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

            third = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            third.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.assertEqual(
            ContactMessage.objects.count(),
            2,
        )

    def test_client_cannot_control_private_fields(self):
        payload = {
            **self.payload,
            "status": "closed",
            "id": "00000000-0000-0000-0000-000000000001",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        saved = ContactMessage.objects.get()

        self.assertEqual(
            saved.status,
            ContactMessage.Status.NEW,
        )

        self.assertNotEqual(
            str(saved.pk),
            payload["id"],
        )

        self.assertNotIn(
            "status",
            response.data,
        )
