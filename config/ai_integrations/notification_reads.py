from datetime import datetime
from typing import Annotated
from uuid import UUID

from channels.db import database_sync_to_async
from django.db.models import F
from notifications.access import get_accessible_notifications
from notifications.models import Notification
from pydantic import BaseModel, Field, StrictBool

from .tool_schema import PageNumber, PageSize, WorkspaceSlug, bounded_page

WorkspaceName = Annotated[str, Field(max_length=150)]
ProjectName = Annotated[str, Field(max_length=150)]
TaskTitle = Annotated[str, Field(max_length=200)]


class NotificationResult(BaseModel):
    notification_id: UUID
    event_type: Notification.EventType
    workspace_slug: WorkspaceSlug
    workspace_name: WorkspaceName
    project_id: UUID | None
    project_name: ProjectName | None
    task_id: UUID | None
    task_title: TaskTitle | None
    created_at: datetime
    read_at: datetime | None
    is_read: bool


class NotificationPage(BaseModel):
    results: list[NotificationResult]
    next_page: int | None


class NotificationUnreadCount(BaseModel):
    unread_count: int


def register_notification_reads(server, read_only, user_id, actor):
    @database_sync_to_async
    def fetch_page(account_id, read, page, page_size):
        queryset = get_accessible_notifications(actor(account_id))
        if read is not None:
            queryset = queryset.filter(read_at__isnull=not read)

        rows, next_page = bounded_page(
            queryset.values(
                "event_type",
                "project_id",
                "task_id",
                "created_at",
                "read_at",
                notification_id=F("pk"),
                workspace_slug=F("workspace__slug"),
                workspace_name=F("workspace__name"),
                project_name=F("project__name"),
                task_title=F("task__title"),
            ),
            page,
            page_size,
        )
        return NotificationPage(
            results=[
                NotificationResult(is_read=row["read_at"] is not None, **row)
                for row in rows
            ],
            next_page=next_page,
        )

    @database_sync_to_async
    def fetch_unread_count(account_id):
        count = (
            get_accessible_notifications(actor(account_id))
            .filter(read_at__isnull=True)
            .count()
        )
        return NotificationUnreadCount(unread_count=count)

    @server.tool(annotations=read_only)
    async def teamboard_list_notifications(
        read: StrictBool | None = None,
        page: PageNumber = 1,
        page_size: PageSize = 20,
    ) -> NotificationPage:
        """List accessible notifications newest first. Set read=false for unread only."""
        return await fetch_page(user_id(), read, page, page_size)

    @server.tool(annotations=read_only)
    async def teamboard_get_notification_unread_count() -> NotificationUnreadCount:
        """Count your currently accessible unread notifications."""
        return await fetch_unread_count(user_id())
