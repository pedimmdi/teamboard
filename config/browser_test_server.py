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

chat_workspace, _ = Workspace.objects.get_or_create(
    slug="chat-tests", defaults={"name": "Browser chat tests"},
)
WorkspaceMembership.objects.get_or_create(
    workspace=chat_workspace, user=user, defaults={"role": "owner"},
)
teammate, _ = User.objects.get_or_create(
    email="browser-chat-teammate@example.com", defaults={"is_email_verified": True},
)
teammate.set_password(password)
teammate.save(update_fields=["password"])
WorkspaceMembership.objects.get_or_create(
    workspace=chat_workspace, user=teammate, defaults={"role": "member"},
)

# Dedicated fixtures for inbox counts and reply navigation across message pages.
from django.db import transaction
from projects.models import Project, ProjectMembership
from chats.models import ChatMessage, ConversationParticipant
from chats.services import get_or_create_direct_chat, get_or_create_project_chat
unread_workspace, _ = Workspace.objects.get_or_create(slug="chatunread", defaults={"name": "Chat unread tests"})
for person, role in ((user, "owner"), (teammate, "member")):
    WorkspaceMembership.objects.get_or_create(workspace=unread_workspace, user=person, defaults={"role": role})
for project_name in ("Unread project", "Long history"):
    with transaction.atomic():
        project, _ = Project.objects.get_or_create(workspace=unread_workspace, name=project_name, defaults={"created_by": user})
        ProjectMembership.objects.get_or_create(project=project, user=user, defaults={"role": "manager"})
        ProjectMembership.objects.get_or_create(project=project, user=teammate, defaults={"role": "member"})
    room = get_or_create_project_chat(workspace_slug=unread_workspace.slug, project_id=project.pk, actor=user)
    ChatMessage.objects.filter(conversation=room).delete()
    if project_name == "Unread project":
        ChatMessage.objects.bulk_create([ChatMessage(conversation=room, sender=teammate, content=f"Group update {i}") for i in range(5)])
    else:
        parent = ChatMessage.objects.create(conversation=room, sender=user, content="Original message outside first page")
        ChatMessage.objects.bulk_create([ChatMessage(conversation=room, sender=user, content=f"History {i}") for i in range(32)])
        ChatMessage.objects.create(conversation=room, sender=user, content="Reply across pages", reply_to=parent)
room = get_or_create_direct_chat(workspace_slug=unread_workspace.slug, actor=user, recipient=teammate)
ChatMessage.objects.filter(conversation=room).delete()
ChatMessage.objects.bulk_create([ChatMessage(conversation=room, sender=teammate, content=f"Direct update {i}") for i in range(2)])
ConversationParticipant.objects.filter(conversation__workspace=unread_workspace).update(last_read_message=None, last_read_at=None, last_read_key=None)

call_command("runserver", "127.0.0.1:" + os.environ.get("E2E_BACKEND_PORT", "8100"), use_reloader=False)
