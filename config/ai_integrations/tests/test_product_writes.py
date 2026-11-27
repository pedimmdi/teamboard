import asyncio
from datetime import timedelta
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.db import database_sync_to_async
from comments.models import Comment
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from notifications.models import Notification
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    set_token_value,
)
from projects.models import ProjectMembership
from projects.services import create_project
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMembership

from ai_integrations.tests.http import mcp_test_client

PASSWORD = "MCP writes test password 2026!"


def _token(user, client, scope):
    token = token_urlsafe()
    row = get_access_token_model()(
        user=user, application=client, scope=scope,
        expires=timezone.now() + timedelta(minutes=5), resource=[settings.MCP_LOCAL_RESOURCE],
    )
    set_token_value(row, token)
    row.save()
    return token


async def _call(client, token, name, data):
    response = await client.post("/mcp", headers={
        "Accept": "application/json, text/event-stream", "Authorization": f"Bearer {token}",
        "MCP-Protocol-Version": "2025-11-25",
    }, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": f"teamboard_{name}", "arguments": data}})
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _result(result):
    assert not result.get("isError"), result
    return result["structuredContent"]


def _error(result, code):
    assert result.get("isError"), result
    assert code in result["content"][0]["text"], result


@pytest.fixture
def records(transactional_db):
    users = get_user_model().objects
    owner = users.create_user(email="mcp-owner-write@example.invalid", password=PASSWORD, is_email_verified=True)
    member = users.create_user(email="mcp-member-write@example.invalid", password=PASSWORD, is_email_verified=True)
    workspace = Workspace.objects.create(name="MCP projects")
    WorkspaceMembership.objects.create(workspace=workspace, role="owner", user=owner)
    WorkspaceMembership.objects.create(workspace=workspace, user=member)
    project = create_project(workspace=workspace, name="Launch", created_by=owner)
    membership = ProjectMembership.objects.create(project=project, user=member)
    app = get_application_model().objects.create(
        name="Live test fixture", client_type="public", authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1:6274/callback", client_secret="",
    )
    return owner, member, workspace, project, membership, app


def test_write_scope_idempotency_live_permissions_and_core_services(records):
    owner, member, workspace, project, membership, app = records
    reader = _token(member, app, "teamboard.read")
    writer = _token(member, app, "teamboard.read teamboard.write")
    args = {"workspace_slug": workspace.slug, "project_id": str(project.pk)}
    create_input = {**args, "idempotency_key": str(uuid4()), "title": "بررسی نسخه", "assignee": member.pk}
    notification = Notification.objects.create(
        recipient=member, workspace=workspace, event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
    )
    owner_token = _token(owner, app, "teamboard.read")
    invitation = WorkspaceInvitation.objects.create(
        workspace=workspace, email="mcp-invited@example.invalid", invited_by=owner,
        token_hash="0" * 64, expires_at=timezone.now() - timedelta(days=1),
    )

    async def exercise():
        async with mcp_test_client() as client:
            async def perform(name, values):
                return _result(await _call(client, writer, name, {"idempotency_key": str(uuid4()), **values}))

            _error(await _call(client, reader, "create_task", create_input), "FORBIDDEN")
            first, retry = await asyncio.gather(
                _call(client, writer, "create_task", create_input), _call(client, writer, "create_task", create_input),
            )
            created = _result(first)
            assert _result(retry) == created
            assert await Task.objects.filter(project=project).acount() == 1
            _error(await _call(client, writer, "create_task", {**create_input, "title": "Different"}), "CONFLICT")

            task = {**args, "task_id": created["task_id"]}
            assert (await perform("update_task", {**task, "changes": {"title": "Login ورود", "due_date": None}}))["status"] == "todo"
            assert (await perform("move_task", {**task, "status": "in_review", "placement": "last"}))["status"] == "in_review"
            parent = await perform("create_task_comment", {**task, "body": "یک نظر"})
            reply = await perform("create_task_comment", {**task, "body": "A reply", "reply_to": parent["comment_id"]})
            assert await Comment.objects.filter(pk=reply["comment_id"], reply_to_id=parent["comment_id"]).aexists()
            assert await perform("update_task_comment", {**task, **reply, "body": "Edited"}) == reply
            chat = await perform("start_direct_chat", {"workspace_slug": workspace.slug, "recipient_id": owner.pk})
            assert (await perform("send_chat_message", {"workspace_slug": workspace.slug, **chat, "content": "سلام"}))["message_id"]
            assert (await perform("mark_notification_read", {"notification_id": str(notification.pk)}))["is_read"]
            assert (await perform("mark_notifications_read", {"notification_ids": [str(notification.pk)]}))["updated_count"] == 0
            _error(await _call(client, writer, "mark_notifications_read", {
                "notification_ids": [str(notification.pk), str(uuid4())], "idempotency_key": str(uuid4()),
            }), "NOT_FOUND")

            time = timezone.now() + timedelta(days=2)
            event = await perform("create_calendar_event", {**args, "title": "جلسه",
                "starts_at": time.isoformat(), "ends_at": (time + timedelta(hours=1)).isoformat()})
            assert await perform("update_calendar_event", {**args, "event_id": event["event_id"], "changes": {"title": "Meeting"}}) == event
            reminder = await perform("create_task_reminder", {**task,
                "reminder": {"kind": "absolute", "timezone": "Asia/Tehran", "run_at": time.isoformat()}})
            assert reminder["status"] == "pending"
            target = {**task, "reminder_id": reminder["reminder_id"]}
            assert (await perform("update_task_reminder", {**target, "changes": {"run_at": (time + timedelta(hours=1)).isoformat()}}))["status"] == "pending"
            assert (await perform("cancel_task_reminder", target))["status"] == "cancelled"

            async def read(name, values):
                return _result(await _call(client, reader, name, values))

            window = {**args, "start": (time - timedelta(days=1)).isoformat(), "end": (time + timedelta(days=2)).isoformat()}
            assert len((await read("list_calendar_events", window))["results"]) == 1
            assert len((await read("get_calendar_timeline", window))["results"]) == 1
            assert (await read("list_task_reminders", task))["results"][0]["status"] == "cancelled"
            assert (await read("get_task_report", args))["summary"]["total_tasks"] == 1
            assert (await read("get_report_history", {**args, "period": "7d"}))["previous_results"]
            assert (await read("list_report_workload", args))["results"][0]["assignee"] == member.pk
            assert (await read("get_workspace_dashboard", {"workspace_slug": workspace.slug}))["my_tasks"] == 1
            assert (await read("list_project_members", {**args, "exact_email": member.email}))["results"][0]["user_id"] == member.pk
            assert (await read("get_account_sessions_summary", {}))["active_count"] == 0
            invitations = {"workspace_slug": workspace.slug, "status": "expired"}
            denied = await _call(client, reader, "list_workspace_invitations", invitations)
            _error(denied, "FORBIDDEN")
            opened = _result(await _call(client, owner_token, "list_workspace_invitations", invitations))
            assert opened["results"][0]["id"] == str(invitation.pk)
            assert "token_hash" not in opened["results"][0]

            new_workspace = await perform("create_workspace", {"name": "فضای کاری تازه"})
            scope = {"workspace_slug": new_workspace["slug"]}
            assert await perform("update_workspace", {**scope, "name": "Renamed workspace"}) == new_workspace
            new_project = await perform("create_project", {**scope, "name": "Demo"})
            assert await perform("update_project", {**scope, **new_project, "changes": {"name": "New demo"}}) == new_project

            await database_sync_to_async(membership.delete)()
            _error(await _call(client, writer, "create_task", create_input), "NOT_FOUND")

    asyncio.run(exercise())


def test_task_deletion_requires_first_party_review_and_management_permission(records):
    owner, member, workspace, project, _, app = records
    writer = _token(owner, app, "teamboard.read teamboard.write")
    sensitive = _token(owner, app, "teamboard.read teamboard.write teamboard.sensitive")
    member_sensitive = _token(member, app, "teamboard.read teamboard.write teamboard.sensitive")
    task = Task.objects.create(project=project, title="Task to remove", assignee=owner)
    args = {"workspace_slug": workspace.slug, "project_id": str(project.pk), "task_id": str(task.pk), "idempotency_key": str(uuid4())}

    async def request_review():
        async with mcp_test_client() as client:
            _error(await _call(client, writer, "request_task_deletion", args), "FORBIDDEN")
            _error(await _call(client, member_sensitive, "request_task_deletion", args), "FORBIDDEN")
            return _result(await _call(client, sensitive, "request_task_deletion", args))

    review = asyncio.run(request_review())
    assert "#approval=" in review["review_url"]
    assert Task.objects.filter(pk=task.pk).exists()

    browser = Client(HTTP_HOST="localhost")

    def web_token(user):
        response = browser.post("/api/v1/accounts/login/", {"email": user.email, "password": PASSWORD}, content_type="application/json")
        assert response.status_code == 200, response.content
        return f"Bearer {response.json()['access']}"

    endpoint = f"/api/v1/ai/approvals/tasks/{review['approval_id']}/"
    assert browser.get(endpoint, headers={"Authorization": web_token(member)}).status_code == 404
    headers = {"Authorization": web_token(owner), "Origin": settings.MCP_LOCAL_FRONTEND_ORIGIN}
    assert browser.get(endpoint, headers=headers).json()["task_title"] == task.title
    assert browser.post(endpoint, {"approve": True}, content_type="application/json", headers={
        **headers, "Origin": "http://other.example.invalid",
    }).status_code == 403
    assert Task.objects.filter(pk=task.pk).exists()
    for _ in range(2):
        response = browser.post(endpoint, {"approve": True}, content_type="application/json", headers=headers)
        assert response.status_code == 200, response.content
        assert response.json()["status"] == "approved"
    assert not Task.objects.filter(pk=task.pk).exists()

    assert browser.get("/api/v1/ai/connections/", headers=headers).json()["results"][0]["scopes"] == [
        "teamboard.read", "teamboard.sensitive", "teamboard.write",
    ]
    assert browser.post(f"/api/v1/ai/connections/{app.pk}/revoke/", headers=headers).status_code == 204
    assert browser.get("/api/v1/ai/connections/", headers=headers).json()["results"] == []
    assert get_access_token_model().objects.filter(user=member).exists()
