"""Run the browser test API against a dedicated, explicitly named database."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3100")

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
from notifications.models import Notification
from workspaces.models import Workspace, WorkspaceMembership

workspace, _ = Workspace.objects.get_or_create(name="Browser notifications fixture")
WorkspaceMembership.objects.get_or_create(
    workspace=workspace, user=user,
    defaults={"role": WorkspaceMembership.Role.OWNER},
)
for index in range(21):
    Notification.objects.update_or_create(
        deduplication_key=f"browser-test-notification:{index}",
        defaults={
            "recipient": user,
            "workspace": workspace,
            "event_type": Notification.EventType.WORKSPACE_ROLE_CHANGED,
            "payload": {"old_role": "member", "new_role": "owner"},
            "read_at": None,
        },
    )

call_command("runserver", "127.0.0.1:" + os.environ.get("E2E_BACKEND_PORT", "8100"), use_reloader=False)
