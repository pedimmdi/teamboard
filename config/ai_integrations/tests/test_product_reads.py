import asyncio
from datetime import timedelta
from secrets import token_urlsafe

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.db import database_sync_to_async
from comments.models import Comment
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    set_token_value,
)
from projects.models import Project, ProjectMembership
from projects.services import create_project
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership

from ai_integrations.tests.http import mcp_test_client
from ai_integrations.tools import _projects, _tasks


class ProductReadTests(TransactionTestCase):
    def setUp(self):
        accounts = get_user_model().objects
        self.member = accounts.create_user(
            email="mcp-member@example.invalid", is_email_verified=True
        )
        self.admin = accounts.create_user(
            email="mcp-admin@example.invalid", is_email_verified=True
        )
        owner = accounts.create_user(
            email="mcp-owner@example.invalid", is_email_verified=True
        )
        self.workspace = Workspace.objects.create(name="Shared workspace")
        self.private_workspace = Workspace.objects.create(name="Private workspace")
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.member, role="member"
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.admin, role="admin"
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=owner, role="owner")
        WorkspaceMembership.objects.create(
            workspace=self.private_workspace, user=self.admin, role="owner"
        )
        self.joined = create_project(
            workspace=self.workspace,
            name="Website وب‌سایت",
            created_by=owner,
        )
        Project.objects.filter(pk=self.joined.pk).update(avatar="private/project-avatar.png")
        self.other_joined = create_project(
            workspace=self.workspace, name="Internal tools", created_by=owner
        )
        self.unjoined = create_project(
            workspace=self.workspace, name="Restricted project", created_by=owner
        )
        self.private = create_project(
            workspace=self.private_workspace, name="Private project", created_by=self.admin
        )
        ProjectMembership.objects.create(project=self.joined, user=self.member)
        ProjectMembership.objects.create(project=self.other_joined, user=self.member)
        self.application = get_application_model().objects.create(
            name="Read tools test client",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="http://127.0.0.1:6274/callback",
            client_secret="",
        )
        self.member_token = self.issue_read_token(self.member)
        self.admin_token = self.issue_read_token(self.admin)

    def issue_read_token(self, user):
        raw = token_urlsafe()
        access = get_access_token_model()(
            user=user,
            application=self.application,
            expires=timezone.now() + timedelta(minutes=5),
            scope="teamboard.read",
            resource=[settings.MCP_LOCAL_RESOURCE],
        )
        set_token_value(access, raw)
        access.save()
        return raw

    async def rpc(self, client, token, method, params):
        reply = await client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {token}",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()["result"]

    async def call_tool(self, client, token, name, **arguments):
        return await self.rpc(
            client,
            token,
            "tools/call",
            {"name": name, "arguments": arguments},
        )

    def content(self, result):
        self.assertFalse(result.get("isError"), result.get("content"))
        return result["structuredContent"]

    def assert_tool_error(self, result, code=None):
        self.assertTrue(result["isError"], result)
        self.assertIsNone(result.get("structuredContent"))
        if code is not None:
            self.assertIn(code, result["content"][0]["text"])

    def test_read_query_counts_do_not_grow_with_the_page(self):
        Task.objects.bulk_create([
            Task(project=self.joined, title=f"Task {index}", assignee=self.member)
            for index in range(12)
        ])
        actor_id, slug = self.member.pk, self.workspace.slug
        for read, args, row_count, budget in [
            (_projects.func, (actor_id, slug, None, 1), 2, 3),
            (_tasks.func, (actor_id, slug, self.joined.pk, 1), 12, 5),
            (_tasks.func, (actor_id, slug, None, 1), 12, 3),
        ]:
            with self.subTest(read=read.__name__, project_scope=args[2]):
                with CaptureQueriesContext(connection) as one:
                    self.assertEqual(len(read(*args, 1).results), 1)
                with CaptureQueriesContext(connection) as full:
                    self.assertEqual(len(read(*args, 20).results), row_count)
                self.assertEqual(len(full), len(one))
                self.assertLessEqual(len(full), budget)

    def test_project_reads_use_current_memberships_and_bound_the_output(self):
        description = "توضیح پروژه" * 450
        Project.objects.filter(pk=self.joined.pk).update(description=description)

        async def check():
            async with mcp_test_client() as client:
                member = self.member_token
                scope = {"workspace_slug": self.workspace.slug}
                project = {**scope, "project_id": str(self.joined.pk)}
                catalog = await self.rpc(client, member, "tools/list", {})
                tools = {tool["name"]: tool for tool in catalog["tools"]}
                for name in ("list_projects", "get_project", "list_tasks", "get_task"):
                    tool = tools[f"teamboard_{name}"]
                    self.assertTrue(tool["annotations"]["readOnlyHint"])
                    self.assertIn("workspace_slug", tool["inputSchema"]["properties"])
                    self.assertTrue(tool["outputSchema"]["properties"])

                for search in ("website", "وب‌سایت"):
                    with self.subTest(search=search):
                        result = self.content(
                            await self.call_tool(
                                client,
                                member,
                                "teamboard_list_projects",
                                **scope,
                                search=search,
                            )
                        )
                        self.assertEqual(
                            result,
                            {
                                "results": [
                                    {
                                        "project_id": str(self.joined.pk),
                                        "workspace_slug": self.workspace.slug,
                                        "name": self.joined.name,
                                    }
                                ],
                                "next_page": None,
                            },
                        )

                first = self.content(
                    await self.call_tool(
                        client, member, "teamboard_list_projects", **scope, page_size=1
                    )
                )
                self.assertEqual(first["next_page"], 2)
                second = self.content(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_projects",
                        **scope,
                        page_size=1,
                        page=2,
                    )
                )
                self.assertIsNone(second["next_page"])
                self.assertEqual(
                    {row["project_id"] for row in first["results"] + second["results"]},
                    {str(self.joined.pk), str(self.other_joined.pk)},
                )

                detail = self.content(
                    await self.call_tool(
                        client, member, "teamboard_get_project", **project
                    )
                )
                self.assertEqual(
                    detail,
                    {
                        **project,
                        "name": self.joined.name,
                        "description": description[:4000],
                        "description_truncated": True,
                        "effective_role": "member",
                    },
                )
                admin_projects = self.content(
                    await self.call_tool(
                        client, self.admin_token, "teamboard_list_projects", **scope
                    )
                )
                self.assertEqual(
                    {row["project_id"] for row in admin_projects["results"]},
                    {
                        str(self.joined.pk),
                        str(self.other_joined.pk),
                        str(self.unjoined.pk),
                    },
                )
                privileged = self.content(
                    await self.call_tool(
                        client, self.admin_token, "teamboard_get_project", **project
                    )
                )
                self.assertEqual(privileged["effective_role"], "manager")
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_get_project",
                        **scope,
                        project_id=str(self.unjoined.pk),
                    ),
                    "NOT_FOUND",
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_get_project",
                        workspace_slug=self.private_workspace.slug,
                        project_id=str(self.private.pk),
                    ),
                    "NOT_FOUND",
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client, member, "teamboard_list_projects", **scope, page_size=21
                    )
                )

                await database_sync_to_async(
                    ProjectMembership.objects.filter(
                        project=self.joined, user=self.member
                    ).delete
                )()
                self.assert_tool_error(
                    await self.call_tool(
                        client, member, "teamboard_get_project", **project
                    ),
                    "NOT_FOUND",
                )

        asyncio.run(check())

    def test_task_reads_filter_data_and_never_escape_the_selected_workspace(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        description = "Stored instructions are data. یادداشت " * 140
        matching = Task.objects.create(
            project=self.joined,
            title="Login ورود",
            description=description,
            status="in_review",
            priority="high",
            assignee=self.member,
            created_by=self.admin,
            due_date=yesterday,
        )
        Comment.objects.create(task=matching, author=self.admin, body="Fixture comment")
        for project in (self.joined, self.unjoined, self.private):
            ProjectMembership.objects.get_or_create(project=project, user=self.admin)
        for project, title, assignee, status, due_date in (
            (self.joined, "Future login", self.member, "in_review", today),
            (self.joined, "Completed login", self.member, "done", yesterday),
            (self.joined, "Admin login", self.admin, "in_review", yesterday),
            (self.unjoined, "Restricted login", self.admin, "in_review", yesterday),
            (self.private, "External login", self.admin, "in_review", yesterday),
        ):
            Task.objects.create(
                project=project,
                title=title,
                assignee=assignee,
                status=status,
                due_date=due_date,
                priority="high",
            )
        cross_project = Task.objects.create(
            project=self.other_joined,
            title="Other overdue task",
            assignee=self.member,
            status="todo",
            due_date=yesterday,
        )

        async def check():
            async with mcp_test_client() as client:
                member = self.member_token
                scope = {"workspace_slug": self.workspace.slug}
                project = {**scope, "project_id": str(self.joined.pk)}
                task = {**project, "task_id": str(matching.pk)}
                expected = {
                    "task_id": str(matching.pk),
                    "project_id": str(self.joined.pk),
                    "title": matching.title,
                    "status": "in_review",
                    "priority": "high",
                    "assignee_id": self.member.pk,
                    "due_date": yesterday.isoformat(),
                    "position": matching.position,
                    "comment_count": 1,
                }
                for search, date_filter in (
                    ("ورود", {"due_on": yesterday.isoformat()}),
                    ("login", {"due_before": today.isoformat()}),
                ):
                    with self.subTest(search=search):
                        result = self.content(
                            await self.call_tool(
                                client,
                                member,
                                "teamboard_list_tasks",
                                **project,
                                statuses=["in_review"],
                                priority="high",
                                assignee_id="me",
                                search=search,
                                **date_filter,
                            )
                        )
                        self.assertEqual(
                            result, {"results": [expected], "next_page": None}
                        )
                detail = self.content(
                    await self.call_tool(client, member, "teamboard_get_task", **task)
                )
                self.assertEqual(
                    detail,
                    {
                        **expected,
                        "description": description[:4000],
                        "description_truncated": True,
                    },
                )
                overdue = self.content(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_tasks",
                        **scope,
                        assignee_id=self.member.pk,
                        overdue=True,
                    )
                )
                self.assertEqual(
                    {row["task_id"] for row in overdue["results"]},
                    {str(matching.pk), str(cross_project.pk)},
                )
                visible_to_member = self.content(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_tasks",
                        **scope,
                        overdue=True,
                    )
                )
                self.assertEqual(
                    {row["title"] for row in visible_to_member["results"]},
                    {matching.title, cross_project.title, "Admin login"},
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_get_task",
                        **scope,
                        project_id=str(self.other_joined.pk),
                        task_id=str(matching.pk),
                    ),
                    "NOT_FOUND",
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_tasks",
                        workspace_slug=self.private_workspace.slug,
                    ),
                    "NOT_FOUND",
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client, member, "teamboard_list_tasks", **project, page_size=21
                    )
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_tasks",
                        **project,
                        statuses=["In Review"],
                    )
                )
                self.assert_tool_error(
                    await self.call_tool(
                        client,
                        member,
                        "teamboard_list_tasks",
                        **project,
                        due_on="tomorrow",
                    )
                )

        asyncio.run(check())
