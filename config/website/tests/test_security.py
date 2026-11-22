
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from website.models import ContactMessage


class ContactSecurityTests(APITestCase):
    def setUp(self):
        cache.clear()

        self.url = reverse(
            "website_api_v1:contact_submit"
        )

        self.payload = {
            "name": "Alex Johnson",
            "email": "alex@example.com",
            "subject": "Question about Teamboard",
            "message": "I have a question about your service.",
        }

    def test_filled_honeypot_does_not_save_message(self):
        response = self.client.post(
            self.url,
            {
                **self.payload,
                "website_url": "https://spam.example",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data,
            {"detail": "Your message has been received."},
        )

        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_empty_honeypot_allows_normal_submission(self):
        response = self.client.post(
            self.url,
            {
                **self.payload,
                "website_url": "",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_oversized_json_payload_returns_413(self):
        response = self.client.post(
            self.url,
            {
                **self.payload,
                "message": "x" * 40000,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            413,
        )

        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_malformed_json_returns_400(self):
        response = self.client.generic(
            "POST",
            self.url,
            data='{"name":',
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_forwarded_ip_header_cannot_bypass_throttle(self):
        with patch(
            "rest_framework.throttling."
            "ScopedRateThrottle.THROTTLE_RATES",
            {"website_contact": "2/hour"},
        ):
            first = self.client.post(
                self.url,
                self.payload,
                format="json",
                HTTP_X_FORWARDED_FOR="198.51.100.10",
            )

            second = self.client.post(
                self.url,
                self.payload,
                format="json",
                HTTP_X_FORWARDED_FOR="198.51.100.11",
            )

            third = self.client.post(
                self.url,
                self.payload,
                format="json",
                HTTP_X_FORWARDED_FOR="198.51.100.12",
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        self.assertEqual(
            third.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.assertEqual(ContactMessage.objects.count(), 2)

    def test_null_character_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                **self.payload,
                "message": "Hello\x00world",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_multiline_unicode_message_is_valid(self):
        response = self.client.post(
            self.url,
            {
                **self.payload,
                "name": "علی رضایی",
                "message": "سلام!\nیک سؤال درباره تیم‌برد دارم.",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        saved = ContactMessage.objects.get()

        self.assertEqual(saved.name, "علی رضایی")
        self.assertIn("سلام!", saved.message)
