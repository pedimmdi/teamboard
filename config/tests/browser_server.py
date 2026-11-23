"""Run the browser test API against a dedicated, explicitly named database."""
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3100")
os.environ["CACHE_KEY_PREFIX"] = f"teamboard:e2e:{uuid4()}"

import django
from django.core.management import call_command

if os.environ.get("POSTGRES_DB") != "teamboard_e2e":
    raise SystemExit("Set POSTGRES_DB=teamboard_e2e for browser tests.")
password = os.environ["E2E_PASSWORD"]
from django.conf import settings

# The browser matrix shares one loopback IP and restores sessions on full reloads.
# Production auth limits are exercised by the API suites.
settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({"login": "120/min", "token_refresh": "240/min"})
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

# Reminder fixture uses a separate account so existing notification totals stay stable.
from datetime import timedelta
from django.utils import timezone
from tasks.models import Task, TaskReminder
from tasks.reminders import process_reminder
reminder_user, _ = User.objects.get_or_create(email="browser-reminder@example.com", defaults={"is_email_verified": True})
reminder_user.set_password(password)
reminder_user.save(update_fields=["password"])
reminder_workspace, _ = Workspace.objects.get_or_create(slug="reminders", defaults={"name": "Reminder browser tests"})
WorkspaceMembership.objects.get_or_create(workspace=reminder_workspace, user=reminder_user, defaults={"role":"owner"})
with transaction.atomic():
    reminder_project, _ = Project.objects.get_or_create(workspace=reminder_workspace, name="Reminder project", defaults={"created_by":reminder_user})
    ProjectMembership.objects.get_or_create(project=reminder_project, user=reminder_user, defaults={"role":"manager"})
reminder_task, _ = Task.objects.get_or_create(project=reminder_project, title="Reminder browser task", defaults={"assignee":reminder_user})
TaskReminder.objects.filter(task=reminder_task).delete()
Notification.objects.filter(recipient=reminder_user).delete()
Task.objects.filter(pk=reminder_task.pk).update(status="todo",due_date=timezone.now().date()+timedelta(days=10))
seed_reminder = TaskReminder.objects.create(task=reminder_task,recipient=reminder_user,kind="absolute",timezone="UTC",run_at=timezone.now()-timedelta(minutes=2))
process_reminder(seed_reminder.pk)

dashboard_empty, _ = Workspace.objects.get_or_create(slug="dashempty", defaults={"name":"Dashboard empty workspace"})
WorkspaceMembership.objects.get_or_create(workspace=dashboard_empty, user=reminder_user, defaults={"role":"owner"})

quality_user, _ = User.objects.get_or_create(email="browser-quality@example.com", defaults={"is_email_verified": True})
quality_user.set_password(password)
quality_user.save(update_fields=["password"])
quality_workspace, _ = Workspace.objects.get_or_create(slug="uiquality", defaults={"name": "UI quality workspace"})
WorkspaceMembership.objects.get_or_create(workspace=quality_workspace, user=quality_user, defaults={"role": "owner"})
with transaction.atomic():
    quality_project, _ = Project.objects.get_or_create(workspace=quality_workspace, name="UI quality project", defaults={"created_by": quality_user})
    ProjectMembership.objects.get_or_create(project=quality_project, user=quality_user, defaults={"role": "manager"})
if not quality_project.tasks.exists():
    statuses = tuple(Task.Status.values)
    Task.objects.bulk_create([
        Task(project=quality_project, title=f"Quality task {index:03}", assignee=quality_user,
             created_by=quality_user, status=statuses[index % len(statuses)],
             position=(index // len(statuses) + 1) * 1024,
             due_date=timezone.now().date() + timedelta(days=index % 16 - 5))
        for index in range(240)
    ])

from website.models import BlogPost
for number in range(11):
    BlogPost.objects.update_or_create(slug=f"website-{number}", defaults={"title":f"Website article {number}", "excerpt":"Ideas for better teamwork.", "content":"## A clearer workflow\n\nWork together.\n\n<script>window.websiteUnsafe=true</script>\n\n[Unsafe](javascript:alert(1))", "status":"published", "published_at":timezone.now()-timedelta(days=number+1)})
BlogPost.objects.filter(slug="website-0").update(
    title_fa="اولین نوشته تیم‌برد",
    excerpt_fa="ایده‌هایی برای کار تیمی بهتر.",
    content_fa="## روالی روشن‌تر\n\nبا هم کار کنید.",
)
call_command("runserver", "127.0.0.1:" + os.environ.get("E2E_BACKEND_PORT", "8100"), use_reloader=False)
