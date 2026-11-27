from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from channels.db import database_sync_to_async
from dashboard.services import get_workspace_dashboard
from django.http import Http404
from django.utils import timezone
from mcp.server.mcpserver.exceptions import ToolError
from projects.access import (
    get_accessible_workspace_project_ids,
    get_workspace_project_membership_or_404,
)
from projects.models import Project
from pydantic import BaseModel, Field, StrictInt
from reports.analytics import filter_current_tasks, history_report, workload_rows
from reports.services import get_task_overview
from tasks.models import Task
from workspaces.access import get_membership_or_404

from .tool_schema import PageNumber, PageSize, WorkspaceSlug

ReportAssignee = Annotated[StrictInt, Field(gt=0, le=2**63 - 1)] | Literal["me"]


class ReportTaskTotals(BaseModel):
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    unassigned_tasks: int
    active_tasks: int
    completion_rate: float


class TaskReportOverview(BaseModel):
    as_of: date
    summary: ReportTaskTotals
    status_distribution: dict[Task.Status, int]
    priority_distribution: dict[Task.Priority, int]


class ReportHistoryBucket(BaseModel):
    date: date
    start_date: date
    end_date: date
    created: int
    completed: int


class ReportHistory(BaseModel):
    start_date: date
    end_date: date
    completion_tracking_since: datetime | None
    results: list[ReportHistoryBucket]
    previous_results: list[ReportHistoryBucket]


class WorkloadItem(BaseModel):
    assignee: int | None
    total_tasks: int
    completed_tasks: int
    active_tasks: int
    overdue_tasks: int
    due_soon_tasks: int
    completion_rate: float


class WorkloadPage(BaseModel):
    results: list[WorkloadItem]
    next_page: int | None


class PersonalDashboard(BaseModel):
    workspace_id: UUID
    workspace_name: str
    as_of: date
    due_soon_until: date
    upcoming_until: datetime
    today_tasks_count: int
    my_tasks: int
    follow_up: int
    overdue_tasks: int
    due_soon_tasks: int
    completed_tasks: int
    projects: int
    upcoming_reminders: int
    upcoming_events: int
    unread_notifications: int


def _projects(slug, project_id, user):
    try:
        if project_id is not None:
            access = get_workspace_project_membership_or_404(
                workspace_slug=slug, project_id=project_id, user=user
            )
            return Project.objects.filter(pk=access.project_id)

        return Project.objects.filter(pk__in=get_accessible_workspace_project_ids(
            workspace_slug=slug, user=user
        ))
    except Http404:
        raise ToolError("NOT_FOUND: Workspace or project unavailable.") from None


def _filters(status, priority, assignee):
    return {key: value for key, value in (
        ("status", status), ("priority", priority), ("assignee", assignee)
    ) if value is not None}


def register_report_reads(server, read_only, user_id, actor):
    @database_sync_to_async
    def overview(account_id, slug, project_id):
        projects = _projects(slug, project_id, actor(account_id))
        today = timezone.localdate()
        totals, status, priority = get_task_overview(Task.objects.filter(project__in=projects), today)
        return TaskReportOverview(
            as_of=today, summary=ReportTaskTotals(**totals),
            status_distribution=status, priority_distribution=priority,
        )

    @database_sync_to_async
    def history(account_id, slug, project_id, filters):
        user = actor(account_id)
        projects = _projects(slug, project_id, user)
        return ReportHistory(**history_report(projects, filters, user, timezone.localdate()))

    @database_sync_to_async
    def workload(account_id, slug, project_id, filters, page, page_size):
        user = actor(account_id)
        projects = _projects(slug, project_id, user)
        tasks = filter_current_tasks(Task.objects.filter(project__in=projects), filters, user)
        rows = list(workload_rows(
            tasks, timezone.localdate(), start=(page - 1) * page_size, limit=page_size + 1
        ))
        return WorkloadPage(
            results=[WorkloadItem(**row) for row in rows[:page_size]],
            next_page=page + 1 if len(rows) > page_size and page < 100 else None,
        )

    @database_sync_to_async
    def dashboard(account_id, slug):
        user = actor(account_id)
        try:
            workspace = get_membership_or_404(slug=slug, user=user).workspace
            result = get_workspace_dashboard(workspace=workspace, user=user)
        except Http404:
            raise ToolError("NOT_FOUND: Workspace unavailable.") from None
        sections = ("my_tasks", "follow_up", "overdue_tasks", "due_soon_tasks", "completed_tasks",
                    "projects", "upcoming_reminders", "upcoming_events")
        return PersonalDashboard(
            workspace_id=result["workspace_id"], workspace_name=result["workspace_name"],
            as_of=result["as_of"], due_soon_until=result["due_soon_until"],
            upcoming_until=result["upcoming_until"], today_tasks_count=result["today_tasks_count"],
            unread_notifications=result["recent_notifications"]["unread_count"],
            **{section: result[section]["count"] for section in sections},
        )

    @server.tool(annotations=read_only)
    async def teamboard_get_task_report(
        workspace_slug: WorkspaceSlug, project_id: UUID | None = None,
    ) -> TaskReportOverview:
        """Get current task totals, completion rate, and status and priority counts in your scope."""
        return await overview(user_id(), workspace_slug, project_id)

    @server.tool(annotations=read_only)
    async def teamboard_get_report_history(
        workspace_slug: WorkspaceSlug, project_id: UUID | None = None,
        period: Literal["7d", "30d", "90d"] = "30d", granularity: Literal["day", "week"] = "week",
        status: Task.Status | None = None, priority: Task.Priority | None = None,
        assignee: ReportAssignee | None = None,
    ) -> ReportHistory:
        """Compare created and completed tasks with the previous matching period in UTC."""
        return await history(user_id(), workspace_slug, project_id, {
            **_filters(status, priority, assignee), "period": period, "granularity": granularity,
        })

    @server.tool(annotations=read_only)
    async def teamboard_list_report_workload(
        workspace_slug: WorkspaceSlug, project_id: UUID | None = None,
        status: Task.Status | None = None, priority: Task.Priority | None = None,
        assignee: ReportAssignee | None = None, page: PageNumber = 1, page_size: PageSize = 20,
    ) -> WorkloadPage:
        """List task counts and upcoming deadlines per assignee in the accessible scope."""
        return await workload(
            user_id(), workspace_slug, project_id, _filters(status, priority, assignee), page, page_size
        )

    @server.tool(annotations=read_only)
    async def teamboard_get_workspace_dashboard(workspace_slug: WorkspaceSlug) -> PersonalDashboard:
        """Get your dashboard task, reminder, calendar and unread notification counts in one workspace."""
        return await dashboard(user_id(), workspace_slug)
