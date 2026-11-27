"""Start the local MCP browser fixture on the dedicated test database."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

if os.environ.get("POSTGRES_DB") != "teamboard_e2e":
    raise SystemExit("Set POSTGRES_DB=teamboard_e2e for the MCP browser fixture.")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.mcp_local_settings"
os.environ["CACHE_KEY_PREFIX"] = f"teamboard:mcp-e2e:{uuid4()}"

import django
from django.conf import settings
from django.core.management import call_command

django.setup()
call_command("migrate", interactive=False)

import uvicorn
from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model

user, _ = get_user_model().objects.get_or_create(
    email="mcp-browser@example.invalid",
    defaults={"is_email_verified": True},
)
user.is_email_verified = True
user.set_password(os.environ["E2E_PASSWORD"])
user.save(update_fields=["password", "is_email_verified"])
get_application_model().objects.update_or_create(
    client_id="teamboard-local-browser-test",
    defaults={
        "name": "Browser fixture",
        "client_type": "public",
        "authorization_grant_type": "authorization-code",
        "client_secret": "",
        "redirect_uris": settings.MCP_LOCAL_FRONTEND_ORIGIN + "/mcp-test-callback",
        "skip_authorization": False,
    },
)
uvicorn.run(
    "config.mcp_local_asgi:application",
    host="127.0.0.1",
    port=urlsplit(settings.MCP_LOCAL_ISSUER).port,
    lifespan="on",
    proxy_headers=False,
    access_log=False,
)
