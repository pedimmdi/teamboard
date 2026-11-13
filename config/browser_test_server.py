"""Run the browser test API against a dedicated, explicitly named database."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["FRONTEND_URL"] = "http://localhost:3100"

import django
from django.core.management import call_command

if os.environ.get("POSTGRES_DB") != "teamboard_e2e":
    raise SystemExit("Set POSTGRES_DB=teamboard_e2e for browser tests.")
password = os.environ["E2E_PASSWORD"]
django.setup()
call_command("migrate", interactive=False)
from django.contrib.auth import get_user_model

User = get_user_model()
user, created = User.objects.get_or_create(
    email="browser-test@example.com", defaults={"is_email_verified": True},
)
user.set_password(password)
user.save(update_fields=["password"])
call_command("runserver", "127.0.0.1:8100", use_reloader=False)
