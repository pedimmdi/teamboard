"""Opt-in MCP application settings for an explicitly configured HTTPS origin."""

import json
from urllib.parse import urlsplit

from ai_integrations.security import is_public_https_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

from . import settings as base
from .mcp_oauth_settings import OAUTH_LOGGING, oauth_settings
from .settings import *  # noqa: F403

MCP_LOCAL_ISSUER = base.env("TEAMBOARD_MCP_ISSUER")
MCP_LOCAL_FRONTEND_ORIGIN = base.FRONTEND_URL
if not all(is_public_https_url(url, origin=True) for url in (MCP_LOCAL_ISSUER, MCP_LOCAL_FRONTEND_ORIGIN)):
    raise ImproperlyConfigured("The MCP issuer and TeamBoard frontend must be explicit HTTPS origins.")

try:
    MCP_CLIENT_CALLBACKS = json.loads(base.env("TEAMBOARD_MCP_ALLOWED_CALLBACKS", default="{}"))
except ValueError as error:
    raise ImproperlyConfigured("TEAMBOARD_MCP_ALLOWED_CALLBACKS must be a JSON object.") from error
if not isinstance(MCP_CLIENT_CALLBACKS, dict) or not all(
    is_public_https_url(uri) and isinstance(label, str) and 1 <= len(label.strip()) <= 80
    for uri, label in MCP_CLIENT_CALLBACKS.items()
):
    raise ImproperlyConfigured("Each allowed callback must be an exact HTTPS URL with a client label.")

MCP_LOCAL_RESOURCE = MCP_LOCAL_ISSUER + "/mcp"
MCP_LOOPBACK_ONLY = False
ALLOWED_HOSTS = [urlsplit(MCP_LOCAL_ISSUER).hostname]
DEBUG = False
ROOT_URLCONF = "config.mcp_local_urls"
INSTALLED_APPS = [*base.INSTALLED_APPS, "oauth2_provider", "ai_integrations"]
CORS_ALLOW_HEADERS = (*default_headers, "x-teamboard-ai-interaction")
CORS_ALLOWED_ORIGINS = [MCP_LOCAL_FRONTEND_ORIGIN]
CSRF_TRUSTED_ORIGINS = [MCP_LOCAL_FRONTEND_ORIGIN]
REFRESH_TOKEN_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
OAUTH2_PROVIDER = oauth_settings(MCP_LOCAL_ISSUER, ["https"], confidential=True)
OAUTH2_PROVIDER["DCR_ENABLED"] = bool(MCP_CLIENT_CALLBACKS)
LOGGING = OAUTH_LOGGING
