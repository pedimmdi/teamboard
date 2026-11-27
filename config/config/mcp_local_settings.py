"""Explicitly opt in to the local MCP environment using Uvicorn."""

from urllib.parse import urlsplit

from ai_integrations.security import is_loopback_http_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

from . import settings as base
from .mcp_oauth_settings import OAUTH_LOGGING, oauth_settings
from .settings import *  # noqa: F403

MCP_LOCAL_ISSUER = base.env(
    "TEAMBOARD_MCP_LOCAL_ISSUER", default="http://localhost:8118"
)
if not all(
    is_loopback_http_url(url, origin=True)
    for url in (MCP_LOCAL_ISSUER, base.FRONTEND_URL)
):
    raise ImproperlyConfigured(
        "The local MCP and frontend origins must be explicit HTTP loopback origins."
    )
if urlsplit(MCP_LOCAL_ISSUER).hostname != urlsplit(base.FRONTEND_URL).hostname:
    raise ImproperlyConfigured(
        "The local MCP issuer and frontend must use the same loopback hostname."
    )

MCP_LOCAL_RESOURCE = MCP_LOCAL_ISSUER + "/mcp"
MCP_LOOPBACK_ONLY = True
MCP_CLIENT_CALLBACKS = {}
MCP_LOCAL_FRONTEND_ORIGIN = base.FRONTEND_URL
ALLOWED_HOSTS = [urlsplit(MCP_LOCAL_ISSUER).hostname]
DEBUG = False
ROOT_URLCONF = "config.mcp_local_urls"
INSTALLED_APPS = [*base.INSTALLED_APPS, "oauth2_provider", "ai_integrations"]
CORS_ALLOW_HEADERS = (*default_headers, "x-teamboard-ai-interaction")
CORS_ALLOWED_ORIGINS = [base.FRONTEND_URL]

OAUTH2_PROVIDER = oauth_settings(MCP_LOCAL_ISSUER, ["http"])
LOGGING = OAUTH_LOGGING
