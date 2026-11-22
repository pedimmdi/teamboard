from django.test import SimpleTestCase

from reports.api.v1.analytics_views import safe_csv_text


class CSVTextTests(SimpleTestCase):
    def test_formula_prefixes_and_control_characters_are_escaped(self):
        for value in (
            "=1+1", " =1+1", "  +SUM(A1)", "\t@cmd", "\r-1", "\n=1",
            "\x00=1", "\x1f+1", "\ufeff=1", "ordinary",
        ):
            with self.subTest(value=value):
                escaped = safe_csv_text(value)
                self.assertEqual(escaped, value if value == "ordinary" else "'" + value)
