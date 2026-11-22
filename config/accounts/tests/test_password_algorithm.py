from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model, authenticate


class ProductionPasswordCompatibilityTests(TestCase):
    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
    def test_real_password_algorithm_remains_compatible_with_authentication(self):
        user = get_user_model().objects.create_user(email="pbkdf@example.com", password="Password-test-2026!")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertEqual(authenticate(email=user.email, password="Password-test-2026!"), user)
