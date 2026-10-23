import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import close_old_connections, connections
from rest_framework import response, status
from rest_framework.test import APITestCase, APIClient
from urllib.parse import parse_qs, urlparse
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from .models import Profile, UserSession

User = get_user_model()

REFRESH_COOKIE_NAME = "teamboard_refresh"


def get_refresh_token(response):
    return response.cookies[REFRESH_COOKIE_NAME].value


class UserModelTests(TestCase):
    def test_create_user_hashes_password(self):
        user = User.objects.create_user(
            email="person@example.com",
            password="Test-password-2026!",
        )

        self.assertTrue(user.check_password("Test-password-2026!"))
        self.assertNotEqual(user.password, "Test-password-2026!")

    def test_profile_is_created_automatically(self):
        user = User.objects.create_user(
            email="profile@example.com",
            password="Test-password-2026!",
        )

        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_full_name(self):
        user = User.objects.create_user(
            email="name@example.com",
            password="Test-password-2026!",
        )

        user.profile.first_name = "Alex"
        user.profile.last_name = "Morgan"
        user.profile.save()

        self.assertEqual(user.profile.full_name, "Alex Morgan")

    def test_email_must_be_unique(self):
        User.objects.create_user(
            email="duplicate@example.com",
            password="Test-password-2026!",
        )

        with self.assertRaises(Exception):
            User.objects.create_user(
                email="duplicate@example.com",
                password="Another-password-2026!",
            )

    def test_email_is_normalized_when_creating_user(self):
        user = User.objects.create_user(
            email="  Test.User@EXAMPLE.COM  ",
            password="Test-password-2026!",
        )

        self.assertEqual(user.email, "test.user@example.com")

    def test_profile_full_name_with_first_name_only(self):
        user = User.objects.create_user(
            email="first-only@example.com",
            password="Test-password-2026!",
        )

        user.profile.first_name = "Alex"
        user.profile.last_name = ""
        user.profile.save()

        self.assertEqual(
            user.profile.full_name,
            "Alex",
        )

    def test_profile_full_name_with_last_name_only(self):
        user = User.objects.create_user(
            email="last-only@example.com",
            password="Test-password-2026!",
        )

        user.profile.first_name = ""
        user.profile.last_name = "Morgan"
        user.profile.save()

        self.assertEqual(
            user.profile.full_name,
            "Morgan",
        )

    def test_profile_full_name_with_empty_names(self):
        user = User.objects.create_user(
            email="empty-name@example.com",
            password="Test-password-2026!",
        )

        user.profile.first_name = ""
        user.profile.last_name = ""
        user.profile.save()

        self.assertEqual(
            user.profile.full_name,
            "",
        )


class RegisterAPITests(APITestCase):
    url = "/api/v1/accounts/register/"

    def setUp(self):
        cache.clear()

    def test_register_user_successfully(self):
        response = self.client.post(
            self.url,
            {
                "email": "newuser@example.com",
                "password": "Strong-password-2026!",
                "password_confirm": "Strong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="newuser@example.com")

        self.assertTrue(
            user.check_password("Strong-password-2026!")
        )
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertNotIn("password", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            email="existing@example.com",
            password="Another-strong-2026!",
        )

        response = self.client.post(
            self.url,
            {
                "email": "existing@example.com",
                "password": "Strong-password-2026!",
                "password_confirm": "Strong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            self.url,
            {
                "email": "mismatch@example.com",
                "password": "Strong-password-2026!",
                "password_confirm": "Different-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_invalid_email(self):
        response = self.client.post(
            self.url,
            {
                "email": "not-an-email",
                "password": "Strong-password-2026!",
                "password_confirm": "Strong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(
            email="existing@example.com",
            password="Another-strong-2026!",
        )

        response = self.client.post(
            self.url,
            {
                "email": "EXISTING@EXAMPLE.COM",
                "password": "Strong-password-2026!",
                "password_confirm": "Strong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class JWTAuthenticationTests(APITestCase):
    token_url = "/api/v1/accounts/login/"
    refresh_url = "/api/v1/accounts/refresh/"

    def setUp(self):
        self.password = "Strong-password-2026!"
        self.user = User.objects.create_user(
            email="jwt@example.com",
            password=self.password,
            is_email_verified=True,
        )

    def test_login_returns_access_and_sets_refresh_cookie(self):
        response = self.client.post(
            self.token_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)

        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

        cookie = response.cookies[REFRESH_COOKIE_NAME]
        self.assertTrue(cookie.value)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/v1/accounts/")

    def test_login_rejects_invalid_password(self):
        response = self.client.post(
            self.token_url,
            {
                "email": self.user.email,
                "password": "Wrong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        login_response = self.client.post(
            self.token_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_login_uses_remote_addr_instead_of_forwarded_header(self):
        response = self.client.post(
            self.token_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
            REMOTE_ADDR="192.0.2.10",
            HTTP_X_FORWARDED_FOR="198.51.100.77",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session = UserSession.objects.get(user=self.user)

        self.assertEqual(session.ip_address, "192.0.2.10")


class ConcurrentRefreshTests(TransactionTestCase):
    refresh_url = "/api/v1/accounts/refresh/"

    def setUp(self):
        self.password = "Strong-password-2026!"
        self.user = User.objects.create_user(
            email="concurrent-refresh@example.com",
            password=self.password,
            is_email_verified=True,
        )

        client = APIClient()
        login_response = client.post(
            "/api/v1/accounts/login/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        self.initial_refresh_token = get_refresh_token(
            login_response
        )

    @patch(
        "accounts.api.v1.views.RefreshTokenView.throttle_classes",
        [],
    )
    def test_concurrent_refresh_only_rotates_once(self):
        barrier = Barrier(2)

        def send_refresh_request():
            close_old_connections()

            try:
                client = APIClient()
                client.cookies[REFRESH_COOKIE_NAME] = (
                    self.initial_refresh_token
                )

                barrier.wait(timeout=10)

                response = client.post(self.refresh_url)

                new_cookie = response.cookies.get(
                    REFRESH_COOKIE_NAME
                )

                return (
                    response.status_code,
                    new_cookie.value if new_cookie else None,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(send_refresh_request)
                for _ in range(2)
            ]
            results = [future.result(timeout=30) for future in futures]

        response_statuses = sorted(
            result[0] for result in results
        )

        self.assertEqual(
            response_statuses,
            [
                status.HTTP_200_OK,
                status.HTTP_401_UNAUTHORIZED,
            ],
        )

        successful_refresh_tokens = [
            token
            for response_status, token in results
            if response_status == status.HTTP_200_OK and token
        ]

        self.assertEqual(len(successful_refresh_tokens), 1)

        session = UserSession.objects.get(user=self.user)

        rotated_token = RefreshToken(
            successful_refresh_tokens[0]
        )

        self.assertEqual(
            session.refresh_token_jti,
            str(rotated_token["jti"]),
        )


class AccountEndpointTests(APITestCase):
    me_url = "/api/v1/accounts/me/"
    logout_url = "/api/v1/accounts/logout/"

    def setUp(self):
        self.password = "Strong-password-2026!"
        self.user = User.objects.create_user(
            email="account@example.com",
            password=self.password,
            is_email_verified=True,
        )

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_me_returns_authenticated_user(self):
        login_response = self.client.post(
            "/api/v1/accounts/login/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Bearer {login_response.data['access']}"
            )
        )

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("first_name", response.data)
        self.assertNotIn("password", response.data)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            "/api/v1/accounts/login/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertIn("access", login_response.data)

        access_token = login_response.data["access"]
        refresh_token = get_refresh_token(login_response)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        self.client.cookies[REFRESH_COOKIE_NAME] = refresh_token

        logout_response = self.client.post(self.logout_url)

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_200_OK,
        )

        # Reuse the original refresh token to verify that it was revoked.
        self.client.cookies[REFRESH_COOKIE_NAME] = refresh_token

        refresh_response = self.client.post(
            "/api/v1/accounts/refresh/"
        )

        self.assertIn(
            refresh_response.status_code,
            [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
            ],
        )

    def test_logout_rejects_another_users_refresh_token(self):
        another_user = User.objects.create_user(
            email="another@example.com",
            password="Another-strong-2026!",
            is_email_verified=True,
        )

        own_login = self.client.post(
            "/api/v1/accounts/login/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            own_login.status_code,
            status.HTTP_200_OK,
        )

        another_login = self.client.post(
            "/api/v1/accounts/login/",
            {
                "email": another_user.email,
                "password": "Another-strong-2026!",
            },
            format="json",
        )

        self.assertEqual(
            another_login.status_code,
            status.HTTP_200_OK,
        )

        own_access_token = own_login.data["access"]
        another_refresh_token = get_refresh_token(another_login)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {own_access_token}"
        )
        self.client.cookies[REFRESH_COOKIE_NAME] = (
            another_refresh_token
        )

        response = self.client.post(self.logout_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
)
class PasswordResetAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reset@example.com",
            password="OldStrongPass!928",
        )
        self.request_url = reverse(
            "accounts_api_v1:password_reset_request"
        )
        self.confirm_url = reverse(
            "accounts_api_v1:password_reset_confirm"
        )

    def request_reset(self, email):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                self.request_url,
                {"email": email},
                format="json",
            )

    def test_reset_request_sends_email_for_existing_user(self):
        response = self.request_reset(self.user.email)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            [self.user.email],
        )
        self.assertIn("uid=", mail.outbox[0].body)
        self.assertIn("token=", mail.outbox[0].body)

    def test_reset_request_does_not_reveal_unknown_email(self):
        existing_response = self.request_reset(self.user.email)
        unknown_response = self.request_reset("unknown@example.com")

        self.assertEqual(
            existing_response.status_code,
            unknown_response.status_code,
        )
        self.assertEqual(
            existing_response.data,
            unknown_response.data,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_valid_token_resets_password(self):
        response = self.request_reset(self.user.email)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        email_body = mail.outbox[0].body
        reset_link = email_body.splitlines()
        reset_link = next(
            line for line in reset_link if "uid=" in line
        )

        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(reset_link).query)
        uid = query["uid"][0]
        token = query["token"][0]

        response = self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass!482",
                "password_confirm": "NewStrongPass!482",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("NewStrongPass!482")
        )
        self.assertFalse(
            self.user.check_password("OldStrongPass!928")
        )

    def test_reset_rejects_mismatched_passwords(self):
        response = self.request_reset(self.user.email)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        email_body = mail.outbox[0].body
        reset_link = next(
            line for line in email_body.splitlines()
            if "uid=" in line
        )

        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(reset_link).query)

        response = self.client.post(
            self.confirm_url,
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "NewStrongPass!482",
                "password_confirm": "DifferentStrongPass!731",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("OldStrongPass!928")
        )

    def test_reset_rejects_invalid_token(self):
        response = self.request_reset(self.user.email)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        email_body = mail.outbox[0].body
        reset_link = next(
            line for line in email_body.splitlines()
            if "uid=" in line
        )

        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(reset_link).query)

        response = self.client.post(
            self.confirm_url,
            {
                "uid": query["uid"][0],
                "token": "invalid-token",
                "new_password": "NewStrongPass!482",
                "password_confirm": "NewStrongPass!482",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reset_token_cannot_be_reused(self):
        self.request_reset(self.user.email)

        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "uid=" in line
        )
        query = parse_qs(urlparse(reset_link).query)

        payload = {
            "uid": query["uid"][0],
            "token": query["token"][0],
            "new_password": "NewStrongPass!482",
            "password_confirm": "NewStrongPass!482",
        }

        first_response = self.client.post(
            self.confirm_url,
            payload,
            format="json",
        )
        second_response = self.client.post(
            self.confirm_url,
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reset_rejects_weak_password(self):
        self.request_reset(self.user.email)

        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "uid=" in line
        )
        query = parse_qs(urlparse(reset_link).query)

        response = self.client.post(
            self.confirm_url,
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "123",
                "password_confirm": "123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("OldStrongPass!928")
        )

    def test_password_reset_blacklists_existing_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.user)

        self.request_reset(self.user.email)

        reset_link = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "uid=" in line
        )
        query = parse_qs(urlparse(reset_link).query)

        response = self.client.post(
            self.confirm_url,
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "NewStrongPass!482",
                "password_confirm": "NewStrongPass!482",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post(
            reverse("accounts_api_v1:refresh"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_reset_request_is_case_insensitive_for_email(self):
        response = self.request_reset(
            self.user.email.upper()
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_request_does_not_send_email_for_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.request_reset(self.user.email)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(mail.outbox), 0)


class ProfileAndPasswordAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            password="CurrentStrongPass!928",
        )
        self.client.force_authenticate(user=self.user)

    def test_current_user_returns_profile(self):
        response = self.client.get(
            reverse("accounts_api_v1:me")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("first_name", response.data)
        self.assertIn("last_name", response.data)

    def test_user_can_update_profile(self):
        response = self.client.patch(
            reverse("accounts_api_v1:me"),
            {
                "first_name": "Alex",
                "last_name": "Morgan",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.first_name, "Alex")
        self.assertEqual(self.user.profile.last_name, "Morgan")

    def test_user_cannot_change_email_through_profile(self):
        original_email = self.user.email

        response = self.client.patch(
            reverse("accounts_api_v1:me"),
            {"email": "changed@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_password_change_rejects_wrong_current_password(self):
        response = self.client.post(
            reverse("accounts_api_v1:password_change"),
            {
                "current_password": "WrongPassword!928",
                "new_password": "NewStrongPass!482",
                "password_confirm": "NewStrongPass!482",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("CurrentStrongPass!928")
        )

    def test_password_change_succeeds(self):
        response = self.client.post(
            reverse("accounts_api_v1:password_change"),
            {
                "current_password": "CurrentStrongPass!928",
                "new_password": "NewStrongPass!482",
                "password_confirm": "NewStrongPass!482",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("NewStrongPass!482")
        )
        self.assertFalse(
            self.user.check_password("CurrentStrongPass!928")
        )


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminStrongPass!928",
        )
        self.client.force_login(self.admin_user)

    def test_user_changelist_loads(self):
        response = self.client.get(
            reverse("admin:accounts_user_changelist")
        )

        self.assertEqual(response.status_code, 200)

    def test_user_add_page_loads(self):
        response = self.client.get(
            reverse("admin:accounts_user_add")
        )

        self.assertEqual(response.status_code, 200)

    def test_profile_changelist_loads(self):
        response = self.client.get(
            reverse("admin:accounts_profile_changelist")
        )

        self.assertEqual(response.status_code, 200)

    def test_user_change_page_loads_with_profile_inline(self):
        user = User.objects.create_user(
            email="member@example.com",
            password="MemberStrongPass!928",
        )

        response = self.client.get(
            reverse("admin:accounts_user_change", args=[user.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "first_name")
        self.assertContains(response, "last_name")


class EmailVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def test_registration_creates_unverified_user_and_sends_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/accounts/register/",
                {
                    "email": "newuser@example.com",
                    "password": "Strong-password-2026!",
                    "password_confirm": "Strong-password-2026!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email="newuser@example.com")
        self.assertFalse(user.is_email_verified)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            "Verify your TeamBoard email address",
        )

    def test_unverified_user_cannot_login(self):
        user = User.objects.create_user(
            email="unverified@example.com",
            password="StrongPassword123!",
        )

        response = self.client.post(
            reverse("accounts_api_v1:login"),
            {
                "email": user.email,
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"],
            "Email address is not verified.",
        )

    def test_email_verification_marks_user_as_verified(self):
        user = User.objects.create_user(
            email="verify@example.com",
            password="StrongPassword123!",
        )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.get(
            reverse("accounts_api_v1:email_verify"),
            {"uid": uid, "token": token},
        )

        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_verified_user_can_login(self):
        user = User.objects.create_user(
            email="verified@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )

        response = self.client.post(
            reverse("accounts_api_v1:login"),
            {
                "email": user.email,
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_email_verification_link_cannot_be_reused(self):
        user = User.objects.create_user(
            email="reuse@example.com",
            password="StrongPassword123!",
        )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = reverse("accounts_api_v1:email_verify")
        params = {"uid": uid, "token": token}

        first_response = self.client.get(url, params)
        second_response = self.client.get(url, params)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)

    def test_invalid_verification_token_is_rejected(self):
        user = User.objects.create_user(
            email="invalid@example.com",
            password="StrongPassword123!",
        )

        uid = urlsafe_base64_encode(force_bytes(user.pk))

        response = self.client.get(
            reverse("accounts_api_v1:email_verify"),
            {"uid": uid, "token": "invalid-token"},
        )

        self.assertEqual(response.status_code, 400)

        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_resend_sends_email_for_unverified_user(self):
        user = User.objects.create_user(
            email="resend@example.com",
            password="StrongPassword123!",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("accounts_api_v1:email_resend"),
                {"email": user.email},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_does_not_reveal_unknown_email(self):
        response = self.client.post(
            reverse("accounts_api_v1:email_resend"),
            {"email": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_does_not_send_email_for_verified_user(self):
        User.objects.create_user(
            email="alreadyverified@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )

        response = self.client.post(
            reverse("accounts_api_v1:email_resend"),
            {"email": "alreadyverified@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class SessionManagementAPITests(APITestCase):
    login_url = "/api/v1/accounts/login/"
    sessions_url = "/api/v1/accounts/sessions/"
    revoke_others_url = (
        "/api/v1/accounts/sessions/revoke-others/"
    )
    me_url = "/api/v1/accounts/me/"

    def setUp(self):
        cache.clear()

        self.password = "Strong-password-2026!"
        self.user = User.objects.create_user(
            email="sessions@example.com",
            password=self.password,
            is_email_verified=True,
        )

    def login(self, email=None, password=None):
        response = self.client.post(
            self.login_url,
            {
                "email": email or self.user.email,
                "password": password or self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {
            **response.data,
            "refresh": get_refresh_token(response),
        }

    def authenticate_with(self, access_token):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

    def test_login_creates_a_session(self):
        tokens = self.login()

        session = UserSession.objects.get(user=self.user)

        self.assertTrue(session.is_active)
        self.assertTrue(session.refresh_token_jti)
        self.assertIn("session_id", RefreshToken(tokens["refresh"]))

    def test_list_returns_only_current_users_sessions(self):
        tokens = self.login()
        self.authenticate_with(tokens["access"])

        response = self.client.get(self.sessions_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(UserSession.objects.get(user=self.user).id),
        )
        self.assertTrue(response.data[0]["is_current"])
        self.assertNotIn("refresh_token_jti", response.data[0])

    def test_list_requires_authentication(self):
        response = self.client.get(self.sessions_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_can_revoke_own_session(self):
        tokens = self.login()
        session = UserSession.objects.get(user=self.user)

        self.authenticate_with(tokens["access"])

        response = self.client.delete(
            reverse(
                "accounts_api_v1:session_revoke",
                args=[session.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)

        self.client.credentials()
        self.authenticate_with(tokens["access"])

        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_user_cannot_revoke_another_users_session(self):
        tokens = self.login()

        another_user = User.objects.create_user(
            email="another-session@example.com",
            password="Another-strong-2026!",
            is_email_verified=True,
        )

        other_tokens = self.client.post(
            self.login_url,
            {
                "email": another_user.email,
                "password": "Another-strong-2026!",
            },
            format="json",
        )

        self.assertEqual(
            other_tokens.status_code,
            status.HTTP_200_OK,
        )

        other_session = UserSession.objects.get(user=another_user)

        self.authenticate_with(tokens["access"])

        response = self.client.delete(
            reverse(
                "accounts_api_v1:session_revoke",
                args=[other_session.id],
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        other_session.refresh_from_db()
        self.assertIsNone(other_session.revoked_at)

    def test_revoke_others_preserves_current_session(self):
        first_tokens = self.login()

        second_tokens = self.login()
        second_session = UserSession.objects.get(
            user=self.user,
            refresh_token_jti=str(
                RefreshToken(second_tokens["refresh"])["jti"]
            ),
        )

        first_session = UserSession.objects.exclude(
            id=second_session.id
        ).get(user=self.user)

        self.authenticate_with(second_tokens["access"])

        response = self.client.post(
            self.revoke_others_url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["revoked_count"], 1)

        first_session.refresh_from_db()
        second_session.refresh_from_db()

        self.assertIsNotNone(first_session.revoked_at)
        self.assertIsNone(second_session.revoked_at)
        self.assertTrue(second_session.is_active)

        self.client.credentials()
        self.authenticate_with(first_tokens["access"])

        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.client.credentials()
        self.authenticate_with(second_tokens["access"])

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_revokes_session_and_refresh_token(self):
        tokens = self.login()
        session = UserSession.objects.get(user=self.user)

        self.authenticate_with(tokens["access"])

        response = self.client.post("/api/v1/accounts/logout/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)

        refresh_response = self.client.post(
            "/api/v1/accounts/refresh/"
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.authenticate_with(tokens["access"])

        me_response = self.client.get(self.me_url)

        self.assertEqual(
            me_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_access_token_without_session_id_is_rejected(self):
        tokens = self.login()
        access_token = AccessToken(tokens["access"])
        del access_token["session_id"]

        self.authenticate_with(str(access_token))

        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_access_token_with_invalid_session_id_is_rejected(self):
        tokens = self.login()
        access_token = AccessToken(tokens["access"])
        access_token["session_id"] = str(uuid.uuid4())

        self.authenticate_with(str(access_token))

        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_token_without_session_id_is_rejected(self):
        tokens = self.login()
        refresh_token = RefreshToken(tokens["refresh"])
        del refresh_token["session_id"]

        self.client.cookies[REFRESH_COOKIE_NAME] = str(refresh_token)

        response = self.client.post(
            "/api/v1/accounts/refresh/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class SecurityAndEdgeCaseAPITests(APITestCase):
    login_url = "/api/v1/accounts/login/"
    refresh_url = "/api/v1/accounts/refresh/"
    logout_url = "/api/v1/accounts/logout/"
    me_url = "/api/v1/accounts/me/"
    password_change_url = "/api/v1/accounts/password/change/"
    sessions_url = "/api/v1/accounts/sessions/"

    def setUp(self):
        cache.clear()

        self.password = "Strong-password-2026!"
        self.user = User.objects.create_user(
            email="security@example.com",
            password=self.password,
            is_email_verified=True,
        )

    def login(self, email=None, password=None):
        response = self.client.post(
            self.login_url,
            {
                "email": email or self.user.email,
                "password": password or self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {
            **response.data,
            "refresh": get_refresh_token(response),
        }

    def authenticate_with(self, access_token):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_login_is_case_insensitive_for_email(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email.upper(),
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn(REFRESH_COOKIE_NAME, response.cookies)

    def test_login_creates_session_with_matching_token_claims(self):
        tokens = self.login()

        refresh = RefreshToken(tokens["refresh"])
        access = AccessToken(tokens["access"])

        session = UserSession.objects.get(user=self.user)

        self.assertEqual(
            str(refresh["session_id"]),
            str(session.id),
        )
        self.assertEqual(
            str(access["session_id"]),
            str(session.id),
        )
        self.assertEqual(
            str(refresh["jti"]),
            session.refresh_token_jti,
        )

    def test_multiple_logins_create_independent_sessions(self):
        first_tokens = self.login()
        second_tokens = self.login()

        first_refresh = RefreshToken(first_tokens["refresh"])
        second_refresh = RefreshToken(second_tokens["refresh"])

        self.assertNotEqual(
            first_refresh["session_id"],
            second_refresh["session_id"],
        )

        self.assertEqual(
            UserSession.objects.filter(
                user=self.user,
                revoked_at__isnull=True,
            ).count(),
            2,
        )

    def test_refresh_rejects_session_with_mismatched_jti(self):
        tokens = self.login()

        session = UserSession.objects.get(user=self.user)

        session.refresh_token_jti = "different-jti"
        session.save(update_fields=["refresh_token_jti"])

        response = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_rejects_revoked_session(self):
        tokens = self.login()

        session = UserSession.objects.get(user=self.user)
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])

        response = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_refresh_rejects_expired_session(self):
        tokens = self.login()

        session = UserSession.objects.get(user=self.user)
        session.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        session.save(update_fields=["expires_at"])

        response = self.client.post(
            self.refresh_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_logout_rejects_invalid_refresh_token(self):
        tokens = self.login()
        self.authenticate_with(tokens["access"])

        self.client.cookies[REFRESH_COOKIE_NAME] = (
            "invalid-refresh-token"
        )

        response = self.client.post(self.logout_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_logout_is_idempotently_rejected_for_already_revoked_token(self):
        tokens = self.login()
        self.authenticate_with(tokens["access"])

        first_response = self.client.post(
            self.logout_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        second_response = self.client.post(
            self.logout_url,
            {"refresh": tokens["refresh"]},
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_password_change_rejects_same_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.password_change_url,
            {
                "current_password": self.password,
                "new_password": self.password,
                "password_confirm": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_password_change_rejects_weak_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.password_change_url,
            {
                "current_password": self.password,
                "new_password": "123",
                "password_confirm": "123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.user.refresh_from_db()

        self.assertTrue(
            self.user.check_password(self.password)
        )

    def test_password_change_invalidates_existing_session(self):
        tokens = self.login()

        self.authenticate_with(tokens["access"])

        response = self.client.post(
            self.password_change_url,
            {
                "current_password": self.password,
                "new_password": "NewStrong-password-2026!",
                "password_confirm": "NewStrong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        session = UserSession.objects.get(user=self.user)

        self.assertIsNotNone(session.revoked_at)

        self.client.cookies[REFRESH_COOKIE_NAME] = tokens["refresh"]

        refresh_response = self.client.post(self.refresh_url)

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.authenticate_with(tokens["access"])

        me_response = self.client.get(self.me_url)

        self.assertEqual(
            me_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_password_change_requires_authentication(self):
        response = self.client.post(
            self.password_change_url,
            {
                "current_password": self.password,
                "new_password": "NewStrong-password-2026!",
                "password_confirm": "NewStrong-password-2026!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_session_list_excludes_revoked_sessions(self):
        self.login()
        active_tokens = self.login()

        sessions = list(
            UserSession.objects.filter(user=self.user).order_by("created_at")
        )
        revoked_session = sessions[0]

        revoked_session.revoked_at = timezone.now()
        revoked_session.save(update_fields=["revoked_at"])

        self.authenticate_with(active_tokens["access"])

        response = self.client.get(self.sessions_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(sessions[1].id),
        )

    def test_session_list_excludes_expired_sessions(self):
        self.login()
        active_tokens = self.login()

        sessions = list(
            UserSession.objects.filter(user=self.user).order_by("created_at")
        )
        expired_session = sessions[0]

        expired_session.expires_at = (
            timezone.now() - timezone.timedelta(minutes=1)
        )
        expired_session.save(update_fields=["expires_at"])

        self.authenticate_with(active_tokens["access"])

        response = self.client.get(self.sessions_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(sessions[1].id),
        )

    def test_session_list_marks_only_current_session(self):
        first_tokens = self.login()
        second_tokens = self.login()

        self.authenticate_with(second_tokens["access"])

        response = self.client.get(self.sessions_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(len(response.data), 2)

        current_sessions = [
            item for item in response.data
            if item["is_current"]
        ]

        self.assertEqual(len(current_sessions), 1)

        current_session_id = current_sessions[0]["id"]
        second_session = UserSession.objects.get(
            user=self.user,
            refresh_token_jti=str(
                RefreshToken(second_tokens["refresh"])["jti"]
            ),
        )

        self.assertEqual(
            str(current_session_id),
            str(second_session.id),
        )

    def test_session_revoke_rejects_invalid_uuid(self):
        tokens = self.login()

        self.authenticate_with(tokens["access"])

        response = self.client.delete(
            "/api/v1/accounts/sessions/"
            "00000000-0000-0000-0000-000000000000/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )