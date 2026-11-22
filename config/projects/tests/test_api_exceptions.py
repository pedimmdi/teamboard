from types import SimpleNamespace

from django.db import IntegrityError, OperationalError
from django.test import SimpleTestCase

from config.api_exceptions import api_exception_handler


class DatabaseExceptionTests(SimpleTestCase):
    def test_known_constraint_has_public_conflict_message(self):
        error = IntegrityError("private database details")
        error.__cause__ = Exception()
        error.__cause__.diag = SimpleNamespace(constraint_name="project_requires_manager")
        response = api_exception_handler(error, {})
        self.assertEqual(response.status_code, 409)
        self.assertIn("Assign another manager", response.data["detail"])
        self.assertNotIn("private", response.data["detail"])

    def test_unknown_database_errors_are_not_disguised(self):
        self.assertIsNone(api_exception_handler(IntegrityError("unknown"), {}))
        self.assertIsNone(api_exception_handler(OperationalError("unknown"), {}))

    def test_retryable_transaction_failure_has_conflict_response(self):
        for code in ("40P01", "40001", "55P03"):
            error = OperationalError("private database details")
            error.__cause__ = Exception()
            error.__cause__.sqlstate = code
            self.assertEqual(api_exception_handler(error, {}).status_code, 409)
