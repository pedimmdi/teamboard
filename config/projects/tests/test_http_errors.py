from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path

from config import urls


def invalid_request(request):
    raise SuspiciousOperation("internal request detail")


def denied_request(request):
    raise PermissionDenied("internal permission detail")


def broken_request(request):
    raise RuntimeError("internal exception detail")


handler400 = urls.handler400
handler403 = urls.handler403
handler404 = urls.handler404
handler500 = urls.handler500
urlpatterns = [
    path("api/v1/invalid-test/", invalid_request),
    path("api/v1/denied-test/", denied_request),
    path("api/v1/broken-test/", broken_request),
    path("api-example/broken-test/", broken_request),
]


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class HttpErrorContractTests(SimpleTestCase):
    def test_unknown_api_paths_use_json_and_keep_append_slash(self):
        for url in ("/api/v1/missing-endpoint/", "/api/v2/missing-endpoint/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Not found."})
        self.assertRedirects(
            self.client.get("/api/v1/website/policy"),
            "/api/v1/website/policy/",
            status_code=301,
            fetch_redirect_response=False,
        )

    @override_settings(ROOT_URLCONF=__name__)
    def test_django_api_error_fallbacks_use_public_messages(self):
        client = Client(raise_request_exception=False)
        for route, status, detail in (
            ("invalid-test", 400, "Bad request."),
            ("denied-test", 403, "Permission denied."),
            ("broken-test", 500, "Something went wrong. Please try again."),
        ):
            with (
                self.subTest(status=status),
                self.assertLogs("django", level="WARNING"),
            ):
                response = client.get(f"/api/v1/{route}/")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": detail})
                self.assertNotIn("internal", response.content.decode())

    @override_settings(ROOT_URLCONF=__name__)
    def test_non_api_error_pages_still_use_html(self):
        client = Client(raise_request_exception=False)
        missing = client.get("/missing/")
        with self.assertLogs("django.request", level="ERROR"):
            broken = client.get("/api-example/broken-test/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(broken.status_code, 500)
        for response in (missing, broken):
            self.assertTrue(response["Content-Type"].startswith("text/html"))
