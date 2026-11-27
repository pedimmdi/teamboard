import asyncio
from datetime import timedelta
from secrets import token_hex, token_urlsafe

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
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


@pytest.mark.django_db(transaction=True)
def test_mcp_notifications_follow_inbox_access_and_hide_payload():
    accounts = get_user_model().objects
    user = accounts.create_user(email="inbox@example.invalid", is_email_verified=True)
    other = accounts.create_user(email="other-inbox@example.invalid", is_email_verified=True)
    workspace = Workspace.objects.create(name="Workspace")
    invited_workspace = Workspace.objects.create(name="فضای دعوت")
    WorkspaceMembership.objects.create(workspace=workspace, user=user)
    WorkspaceMembership.objects.create(workspace=workspace, user=other, role="owner")
    project = create_project(workspace=workspace, created_by=other, name="Website")
    project_member = ProjectMembership.objects.create(project=project, user=user)
    task = Task.objects.create(project=project, title="بررسی سایت", assignee=other)
    task_notice = Notification.objects.create(
        recipient=user,
        actor=other,
        workspace=workspace,
        project=project,
        task=task,
        event_type=Notification.EventType.TASK_UPDATED,
        payload={"internal_url": "https://private.example.invalid/task"},
    )
    read_notice = Notification.objects.create(
        recipient=user,
        workspace=workspace,
        event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
        read_at=timezone.now(),
    )
    invitation = WorkspaceInvitation.objects.create(
        workspace=invited_workspace,
        email=user.email,
        invited_by=other,
        token_hash=token_hex(32),
        expires_at=timezone.now() + timedelta(days=1),
    )
    invitation_notice = Notification.objects.create(
        recipient=user,
        actor=other,
        workspace=invited_workspace,
        event_type=Notification.EventType.WORKSPACE_INVITED,
        payload={"invitation_id": str(invitation.pk), "secret": "private-test-value"},
    )
    Notification.objects.create(
        recipient=other,
        workspace=workspace,
        event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
    )
    Notification.objects.create(
        recipient=user,
        workspace=invited_workspace,
        event_type=Notification.EventType.WORKSPACE_ROLE_CHANGED,
    )

    application = get_application_model().objects.create(
        name="Notification test client",
        client_type="public",
        authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1:6274/callback",
        client_secret="",
    )
    token = token_urlsafe()
    access_token = get_access_token_model()(
        user=user,
        application=application,
        expires=timezone.now() + timedelta(minutes=5),
        scope="teamboard.read",
        resource=[settings.MCP_LOCAL_RESOURCE],
    )
    set_token_value(access_token, token)
    access_token.save()

    async def check_notifications():
        async with mcp_test_client() as client:
            client.headers.update({
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {token}",
                "MCP-Protocol-Version": "2025-11-25",
            })
            async def call(name, **arguments):
                response = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                )
                assert response.status_code == 200
                for private_value in (
                    other.email,
                    str(invitation.pk),
                    "private-test-value",
                    "https://private.example.invalid/task",
                ):
                    assert private_value not in response.text
                return response.json()["result"]

            list_tool = "teamboard_list_notifications"
            count_tool = "teamboard_get_notification_unread_count"
            first = (await call(list_tool, read=False, page_size=1))["structuredContent"]
            assert first["next_page"] == 2
            invite_row = first["results"][0]
            assert set(invite_row) == {
                "notification_id", "event_type", "workspace_slug", "workspace_name",
                "project_id", "project_name", "task_id", "task_title", "created_at",
                "read_at", "is_read",
            }
            assert invite_row["notification_id"] == str(invitation_notice.pk)
            assert invite_row["workspace_name"] == "فضای دعوت"
            assert invite_row["is_read"] is False
            assert invite_row["task_id"] is None

            second = (await call(list_tool, read=False, page=2, page_size=1))["structuredContent"]
            assert second["next_page"] is None
            task_row = second["results"][0]
            assert task_row["notification_id"] == str(task_notice.pk)
            assert task_row["project_id"] == str(project.pk)
            assert task_row["task_id"] == str(task.pk)
            assert task_row["task_title"] == "بررسی سایت"

            read_page = (await call(list_tool, read=True))["structuredContent"]
            assert [row["notification_id"] for row in read_page["results"]] == [str(read_notice.pk)]
            assert read_page["results"][0]["is_read"] is True
            assert (await call(count_tool))["structuredContent"] == {"unread_count": 2}
            assert (await call(list_tool, page_size=21))["isError"] is True
            assert (await call(list_tool, read="false"))["isError"] is True

            await database_sync_to_async(project_member.delete)()
            invitations = (await call(list_tool, read=False))["structuredContent"]
            assert [row["notification_id"] for row in invitations["results"]] == [str(invitation_notice.pk)]
            assert (await call(count_tool))["structuredContent"] == {"unread_count": 1}

    asyncio.run(check_notifications())
