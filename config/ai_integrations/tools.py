from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from projects.access import (
    get_accessible_workspace_project_ids,
    get_workspace_project_membership_or_404,
)
from projects.models import Project
from pydantic import BaseModel, BeforeValidator, Field, StrictBool, StrictInt, StrictStr
from tasks.access import get_accessible_project_tasks, get_task_or_404
from tasks.models import Task
from tasks.queries import filter_tasks, with_comment_count
from workspaces.access import get_accessible_workspaces, get_membership_or_404

from .chat_reads import register_chat_reads
from .comment_reads import register_comment_reads
from .file_reads import register_file_reads
from .more_reads import register_more_reads
from .notification_reads import register_notification_reads
from .security import READ_SCOPE
from .tool_schema import PageNumber, PageSize, WorkspaceSlug, bounded_page
from .write_tools import register_write_tools

Search = Annotated[StrictStr, Field(min_length=1, max_length=200)]
AssigneeId = Annotated[StrictInt, Field(gt=0, le=2**63 - 1)] | Literal["me"]
Statuses = Annotated[list[Task.Status], Field(min_length=1, max_length=len(Task.Status))]
DESCRIPTION_LIMIT = 4000


def _civil_date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Use a valid date in YYYY-MM-DD format.")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use a valid date in YYYY-MM-DD format.")
    return parsed


CivilDate = Annotated[date, BeforeValidator(_civil_date)]


class ProfileResult(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str


class WorkspaceResult(BaseModel):
    workspace_id: str
    slug: str
    name: str
    role: str


class WorkspacePage(BaseModel):
    results: list[WorkspaceResult]
    next_page: int | None


class ProjectResult(BaseModel):
    project_id: UUID
    workspace_slug: str
    name: str


class ProjectDetail(ProjectResult):
    description: Annotated[str, Field(max_length=DESCRIPTION_LIMIT)]
    description_truncated: bool
    effective_role: str


class ProjectPage(BaseModel):
    results: list[ProjectResult]
    next_page: int | None


class TaskResult(BaseModel):
    task_id: UUID
    project_id: UUID
    title: str
    status: Task.Status
    priority: Task.Priority
    assignee_id: int | None
    due_date: date | None
    position: int
    comment_count: int


class TaskDetail(TaskResult):
    description: Annotated[str, Field(max_length=DESCRIPTION_LIMIT)]
    description_truncated: bool


class TaskPage(BaseModel):
    results: list[TaskResult]
    next_page: int | None


def _description(text):
    return {
        "description": text[:DESCRIPTION_LIMIT],
        "description_truncated": len(text) > DESCRIPTION_LIMIT,
    }


def _user_id():
    token = get_access_token()
    if token is None or not token.subject or READ_SCOPE not in token.scopes:
        raise ToolError("FORBIDDEN: A TeamBoard read connection is required.")
    return int(token.subject)


def _actor(user_id):
    user = (
        get_user_model()
        .objects.filter(pk=user_id, is_active=True, is_email_verified=True)
        .first()
    )
    if user is None:
        raise ToolError("FORBIDDEN: This TeamBoard account is unavailable.")
    return user


@database_sync_to_async
def _profile(user_id):
    user = _actor(user_id)
    profile = getattr(user, "profile", None)
    return ProfileResult(
        user_id=user.pk,
        email=user.email,
        first_name=profile.first_name if profile else "",
        last_name=profile.last_name if profile else "",
    )


@database_sync_to_async
def _workspaces(user_id, page, page_size):
    user = _actor(user_id)
    queryset = (
        get_accessible_workspaces(user)
        .order_by("name", "pk")
        .values_list("pk", "slug", "name", "memberships__role")
    )
    rows, next_page = bounded_page(queryset, page, page_size)
    return WorkspacePage(
        results=[
            WorkspaceResult(workspace_id=str(pk), slug=slug, name=name, role=role)
            for pk, slug, name, role in rows
        ],
        next_page=next_page,
    )


@database_sync_to_async
def _workspace(user_id, slug):
    user = _actor(user_id)
    try:
        membership = get_membership_or_404(slug, user)
    except Http404:
        raise ToolError("NOT_FOUND: Workspace unavailable.") from None
    return WorkspaceResult(
        workspace_id=str(membership.workspace_id),
        slug=membership.workspace.slug,
        name=membership.workspace.name,
        role=membership.role,
    )


@database_sync_to_async
def _projects(user_id, workspace_slug, search, page, page_size):
    user = _actor(user_id)
    try:
        project_ids = get_accessible_workspace_project_ids(
            workspace_slug=workspace_slug, user=user
        )
    except Http404:
        raise ToolError("NOT_FOUND: Workspace unavailable.") from None
    queryset = Project.objects.filter(pk__in=project_ids)
    if search:
        queryset = queryset.filter(name__icontains=search.strip())
    rows, next_page = bounded_page(
        queryset.order_by("-created_at", "-pk").values_list("pk", "name"),
        page,
        page_size,
    )
    return ProjectPage(
        results=[
            ProjectResult(project_id=pk, workspace_slug=workspace_slug, name=name)
            for pk, name in rows
        ],
        next_page=next_page,
    )


@database_sync_to_async
def _project(user_id, workspace_slug, project_id):
    user = _actor(user_id)
    try:
        access = get_workspace_project_membership_or_404(
            workspace_slug=workspace_slug, project_id=project_id, user=user
        )
    except Http404:
        raise ToolError("NOT_FOUND: Project unavailable.") from None
    return ProjectDetail(
        project_id=access.project.pk,
        workspace_slug=workspace_slug,
        name=access.project.name,
        effective_role=access.role,
        **_description(access.project.description),
    )


@database_sync_to_async
def _tasks(user_id, workspace_slug, project_id, page, page_size, *, overdue=False, **filters):
    user = _actor(user_id)
    try:
        if project_id is None:
            project_ids = get_accessible_workspace_project_ids(
                workspace_slug=workspace_slug, user=user
            )
            queryset = with_comment_count(Task.objects.filter(project_id__in=project_ids))
        else:
            queryset = get_accessible_project_tasks(
                workspace_slug=workspace_slug, project_id=project_id, user=user
            )
    except Http404:
        raise ToolError("NOT_FOUND: Workspace or project unavailable.") from None
    if filters.get("assignee_id") == "me":
        filters["assignee_id"] = user.pk
    if overdue:
        filters["overdue_before"] = timezone.localdate()
    queryset = filter_tasks(queryset, **filters)
    rows, next_page = bounded_page(
        queryset.order_by("-created_at", "-pk").values(
            "pk", "project_id", "title", "status", "priority", "assignee_id",
            "due_date", "position", "comment_count",
        ),
        page,
        page_size,
    )
    return TaskPage(
        results=[TaskResult(task_id=row.pop("pk"), **row) for row in rows],
        next_page=next_page,
    )


@database_sync_to_async
def _task(user_id, workspace_slug, project_id, task_id):
    user = _actor(user_id)
    try:
        result = get_task_or_404(
            workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user
        )
    except Http404:
        raise ToolError("NOT_FOUND: Task unavailable.") from None
    return TaskDetail(
        task_id=result.pk,
        project_id=result.project_id,
        title=result.title,
        status=result.status,
        priority=result.priority,
        assignee_id=result.assignee_id,
        due_date=result.due_date,
        position=result.position,
        comment_count=result.comments.count(),
        **_description(result.description),
    )


def register_read_tools(server):
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    register_chat_reads(server, read_only, _user_id, _actor)
    register_comment_reads(server, read_only, _user_id, _actor)
    register_file_reads(server, read_only, _user_id, _actor)
    register_notification_reads(server, read_only, _user_id, _actor)
    register_more_reads(server, read_only, _user_id, _actor)
    register_write_tools(server, ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ), _actor)

    @server.tool(annotations=read_only)
    async def teamboard_whoami() -> ProfileResult:
        """Return the profile of the TeamBoard account that authorized this connection."""
        return await _profile(_user_id())

    @server.tool(annotations=read_only)
    async def teamboard_list_workspaces(
        page: PageNumber = 1,
        page_size: PageSize = 20,
    ) -> WorkspacePage:
        """List your current TeamBoard workspaces and roles, with at most 20 per page."""
        return await _workspaces(_user_id(), page, page_size)

    @server.tool(annotations=read_only)
    async def teamboard_get_workspace(slug: WorkspaceSlug) -> WorkspaceResult:
        """Get one accessible workspace by its exact slug from teamboard_list_workspaces."""
        return await _workspace(_user_id(), slug)

    @server.tool(annotations=read_only)
    async def teamboard_list_projects(
        workspace_slug: WorkspaceSlug,
        search: Search | None = None,
        page: PageNumber = 1,
        page_size: PageSize = 20,
    ) -> ProjectPage:
        """List accessible projects in an exact workspace slug, newest first. Search by name."""
        return await _projects(_user_id(), workspace_slug, search, page, page_size)

    @server.tool(annotations=read_only)
    async def teamboard_get_project(workspace_slug: WorkspaceSlug, project_id: UUID) -> ProjectDetail:
        """Get a project by exact ID and workspace slug. The role reflects your current access."""
        return await _project(_user_id(), workspace_slug, project_id)

    @server.tool(annotations=read_only)
    async def teamboard_list_tasks(
        workspace_slug: WorkspaceSlug,
        project_id: UUID | None = None,
        statuses: Statuses | None = None,
        priority: Task.Priority | None = None,
        assignee_id: AssigneeId | None = None,
        due_on: CivilDate | None = None,
        due_before: CivilDate | None = None,
        overdue: StrictBool = False,
        search: Search | None = None,
        page: PageNumber = 1,
        page_size: PageSize = 20,
    ) -> TaskPage:
        """List tasks in accessible projects, newest first. Supply a project ID to limit scope.

        Use an exact user ID or 'me' for assignee_id. Search titles and descriptions.
        Use Gregorian YYYY-MM-DD for dates. due_before is exclusive. Overdue excludes done
        tasks and compares due dates with TeamBoard's current UTC date.
        """
        return await _tasks(
            _user_id(), workspace_slug, project_id, page, page_size,
            statuses=statuses,
            priority=priority,
            assignee_id=assignee_id,
            due_on=due_on,
            due_before=due_before,
            overdue=overdue,
            search=search.strip() if search else None,
        )

    @server.tool(annotations=read_only)
    async def teamboard_get_task(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID
    ) -> TaskDetail:
        """Get one task by exact workspace, project and task IDs, including its description."""
        return await _task(_user_id(), workspace_slug, project_id, task_id)
