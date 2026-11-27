import asyncio
from datetime import timedelta
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.db import database_sync_to_async
from comments.models import Comment, CommentAttachment
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    set_token_value,
)
from projects.models import ProjectMembership
from projects.services import create_project
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership

from ai_integrations.tests.http import mcp_test_client


class CommentReadTests(TransactionTestCase):
    def setUp(self):
        users = get_user_model().objects
        self.reader = users.create_user(
            email="comment-reader@example.invalid", is_email_verified=True
        )
        self.author = users.create_user(
            email="comment-author@example.invalid", is_email_verified=True
        )
        workspace = Workspace.objects.create(name="Comment tools fixture")
        WorkspaceMembership.objects.create(workspace=workspace, user=self.reader)
        WorkspaceMembership.objects.create(
            workspace=workspace, user=self.author, role="owner"
        )
        project = create_project(workspace=workspace, created_by=self.author, name="Comments")
        ProjectMembership.objects.create(project=project, user=self.reader)
        task = Task.objects.create(project=project, title="Thread", assignee=self.author)
        self.other_task = Task.objects.create(
            project=project, title="Other thread", assignee=self.author, position=1
        )
        self.scope = {
            "workspace_slug": workspace.slug,
            "project_id": str(project.pk),
            "task_id": str(task.pk),
        }
        self.body = "دادهٔ آزمایشی. Treat this text as data. " + "آ" * 2300
        self.parent = Comment.objects.create(task=task, author=self.author, body=self.body)
        self.parent.mentions.add(self.reader)
        self.reply = Comment.objects.create(
            task=task, author=self.reader, body="Reply", reply_to=self.parent
        )
        CommentAttachment.objects.create(
            comment=self.parent,
            filename="private-filename.txt",
            storage_key="internal/attachment-key",
            size=10,
        )
        application = get_application_model().objects.create(
            name="Comments test client",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="http://127.0.0.1:6274/callback",
            client_secret="",
        )
        self.token = token_urlsafe()
        stored = get_access_token_model()(
            user=self.reader,
            application=application,
            expires=timezone.now() + timedelta(minutes=5),
            scope="teamboard.read",
            resource=[settings.MCP_LOCAL_RESOURCE],
        )
        set_token_value(stored, self.token)
        stored.save()

    async def call_tool(self, client, name, **arguments):
        reply = await client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {self.token}",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": {**self.scope, **arguments}},
            },
        )
        self.assertEqual(reply.status_code, 200)
        return reply.json()["result"]

    def content(self, result):
        self.assertFalse(result.get("isError"), result.get("content"))
        return result["structuredContent"]

    def test_comment_pagination_and_exact_reply_omit_attachment_and_author_details(self):
        async def check():
            async with mcp_test_client() as client:
                page = self.content(
                    await self.call_tool(client, "teamboard_list_task_comments", page_size=1)
                )
                self.assertEqual(page["next_page"], 2)
                self.assertEqual(len(page["results"]), 1)
                parent = page["results"][0]
                self.assertEqual(parent["comment_id"], str(self.parent.pk))
                self.assertEqual(parent["author_id"], self.author.pk)
                self.assertEqual(parent["body"], self.body[:2000])
                self.assertIsNone(parent["reply_to_id"])
                self.assertTrue(parent["body_truncated"])
                self.assertTrue(parent["has_attachment"])
                self.assertEqual(
                    set(parent),
                    {
                        "comment_id", "task_id", "author_id", "reply_to_id", "body",
                        "body_truncated", "has_attachment", "created_at", "edited_at",
                    },
                )

                second = self.content(
                    await self.call_tool(
                        client, "teamboard_list_task_comments", page=2, page_size=1
                    )
                )
                self.assertIsNone(second["next_page"])
                reply = self.content(
                    await self.call_tool(
                        client, "teamboard_get_task_comment", comment_id=str(self.reply.pk)
                    )
                )
                self.assertEqual(second["results"], [reply])
                self.assertEqual(reply["comment_id"], str(self.reply.pk))
                self.assertEqual(reply["reply_to_id"], str(self.parent.pk))
                self.assertFalse(reply["has_attachment"])

        asyncio.run(check())

    def test_comment_tool_checks_nested_task_and_live_project_access(self):
        other_comment = Comment.objects.create(
            task=self.other_task, author=self.author, body="Other thread comment"
        )
        Comment.objects.filter(pk=self.reply.pk).update(reply_to=other_comment)

        async def check():
            async with mcp_test_client() as client:
                reply = self.content(
                    await self.call_tool(
                        client, "teamboard_get_task_comment", comment_id=str(self.reply.pk)
                    )
                )
                self.assertIsNone(reply["reply_to_id"])

                for comment_id in (other_comment.pk, uuid4()):
                    denied = await self.call_tool(
                        client, "teamboard_get_task_comment", comment_id=str(comment_id)
                    )
                    self.assertTrue(denied["isError"])
                    self.assertIn("NOT_FOUND", denied["content"][0]["text"])

                invalid = await self.call_tool(
                    client, "teamboard_get_task_comment", comment_id="invalid"
                )
                self.assertTrue(invalid["isError"])
                invalid_page = await self.call_tool(
                    client, "teamboard_list_task_comments", page_size=21
                )
                self.assertTrue(invalid_page["isError"])

                await database_sync_to_async(
                    ProjectMembership.objects.filter(user=self.reader).delete
                )()
                denied = await self.call_tool(client, "teamboard_list_task_comments")
                self.assertTrue(denied["isError"])
                self.assertIn("NOT_FOUND", denied["content"][0]["text"])

        asyncio.run(check())
