import hashlib
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection

READ_SCOPE = "teamboard.read"
WRITE_SCOPE = "teamboard.write"
SENSITIVE_SCOPE = "teamboard.sensitive"
MCP_SCOPES = {
    READ_SCOPE: "Read TeamBoard records you can access",
    WRITE_SCOPE: "Create and edit TeamBoard records you can manage",
    SENSITIVE_SCOPE: "Request sensitive actions for manual approval in TeamBoard",
}
REFRESH_IDLE_SECONDS = 8 * 60 * 60
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def allowed_scopes(scopes):
    granted = set(scopes)
    return (
        READ_SCOPE in granted
        and granted <= MCP_SCOPES.keys()
        and len(granted) == len(scopes)
        and (SENSITIVE_SCOPE not in granted or WRITE_SCOPE in granted)
    )


def lock_account(user_id):
    # Serialize only MCP mutations and revocation. Existing services sometimes
    # lock a project before the user, so do not hold an account row lock here.
    lock = int.from_bytes(hashlib.sha256(f"teamboard:mcp:{user_id}".encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock])
    return get_user_model().objects.filter(
        pk=user_id, is_active=True, is_email_verified=True,
    ).exists()


def is_loopback_http_url(value, *, origin=False):
    try:
        url = urlsplit(value)
        expected_netloc = f"[{url.hostname}]" if url.hostname == "::1" else url.hostname
        return (
            url.scheme == "http"
            and url.hostname in LOOPBACK_HOSTS
            and url.port is not None
            and url.netloc == f"{expected_netloc}:{url.port}"
            and not url.fragment
            and (not origin or (not url.path and not url.query))
            and not any(ord(character) <= 32 or character == "\\" for character in value)
        )
    except ValueError:
        return False


def is_public_https_url(value, *, origin=False):
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        return (
            parsed.scheme == "https" and parsed.netloc == hostname
            and re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}", hostname)
            and hostname.rsplit(".", 1)[-1] not in {"localhost", "local", "internal", "test", "example", "invalid", "onion"}
            and not parsed.fragment and not (origin and (parsed.path or parsed.query))
            and not any(ord(character) <= 32 or character == "\\" for character in value)
        )
    except ValueError:
        return False


def allowed_callback(uri, *, initial=True):
    return (
        is_loopback_http_url(uri) if settings.MCP_LOOPBACK_ONLY
        else is_public_https_url(uri) and (not initial or uri in settings.MCP_CLIENT_CALLBACKS)
    )


def allowed_client(application):
    if application is None:
        return False
    redirects = application.redirect_uris.split()
    types = {"public"} if settings.MCP_LOOPBACK_ONLY else {"public", "confidential"}
    return application.client_type in types and bool(redirects) and all(map(allowed_callback, redirects))


def within_rate_limit(bucket, limit, *, backend=cache):
    key = f"ai:local:{bucket}"
    if backend.add(key, 1, timeout=60):
        return True
    return backend.incr(key) <= limit
