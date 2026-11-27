from typing import Annotated, Literal
from uuid import UUID

from channels.db import database_sync_to_async
from chats.access import get_conversation_or_404
from chats.services import create_chat_message, get_or_create_direct_chat
from comments.access import get_comment_or_404, get_comment_task_or_404
from comments.api.v1.serializers import CommentCreateSerializer, CommentUpdateSerializer
from comments.services import create_comment, update_comment
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from mcp.server.mcpserver.exceptions import ToolError
from notifications.access import get_accessible_notifications
from notifications.models import Notification
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from tasks.access import get_task_or_404, get_task_project_access_or_404
from tasks.api.v1.serializers import (
    TaskCreateSerializer,
    TaskMoveSerializer,
    TaskUpdateSerializer,
)
from tasks.models import Task
from tasks.services import create_task, move_task, update_task
from workspaces.models import WorkspaceMembership

from .approvals import register_approval_tools
from .mutations import run_idempotent, write_user_id
from .schedule_writes import register_schedule_writes
from .tool_schema import WorkspaceSlug
from .workspace_writes import register_workspace_writes

Title = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Description = Annotated[StrictStr, Field(max_length=10000)]
Text = Annotated[StrictStr, Field(min_length=1, max_length=5000)]
Date = Annotated[StrictStr, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]
UserId = Annotated[StrictInt, Field(gt=0, le=2**63 - 1)]
Position = Annotated[StrictInt, Field(ge=0, le=2**31 - 1)]


class TaskChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    status: Task.Status | None = None
    priority: Task.Priority | None = None
    assignee: UserId | None = None
    due_date: Date | None = None


class TaskWritten(BaseModel):
    task_id: UUID
    status: Task.Status


class CommentWritten(BaseModel):
    comment_id: UUID


class MessageWritten(BaseModel):
    message_id: UUID


class ConversationWritten(BaseModel):
    conversation_id: UUID


class NotificationWritten(BaseModel):
    notification_id: UUID
    is_read: bool


class NotificationsWritten(BaseModel):
    notification_ids: list[UUID]
    updated_count: int


def _validated(serializer_class, data, **context):
    serializer = serializer_class(data=data, context=context)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@database_sync_to_async
def _run(account_id, actor, name, key, arguments, authorize, operation):
    user = actor(account_id)
    try:
        return run_idempotent(user, name, key, arguments, lambda: authorize(user), lambda target: operation(user, target))
    except (Http404, NotFound):
        raise ToolError("NOT_FOUND: The requested TeamBoard record is unavailable.") from None
    except PermissionDenied:
        raise ToolError("FORBIDDEN: You do not have permission for this action.") from None
    except ValidationError as error:
        fields = error.detail if isinstance(error.detail, dict) else ()
        hint = ", ".join(sorted(fields))
        raise ToolError(f"VALIDATION: Check the supplied fields{': ' + hint if hint else '.'}") from None


def _task_record(task):
    return {"task_id": task.pk, "status": task.status}


def register_write_tools(server, annotations, actor):
    async def write(name, key, arguments, authorize, operation):
        return await _run(write_user_id(), actor, name, key, arguments, authorize, operation)

    register_schedule_writes(server, annotations, write, _validated)
    register_workspace_writes(server, annotations, write, _validated)
    register_approval_tools(server, annotations, write)

    @server.tool(annotations=annotations)
    async def teamboard_create_task(
        workspace_slug: WorkspaceSlug, project_id: UUID, idempotency_key: UUID, title: Title,
        assignee: UserId, description: Description = "", status: Task.Status = Task.Status.TODO,
        priority: Task.Priority = Task.Priority.MEDIUM, due_date: Date | None = None,
    ) -> TaskWritten:
        """Create a task with an exact eligible project member ID and a stable retry key."""
        def authorize(user):
            return get_task_project_access_or_404(workspace_slug=workspace_slug, project_id=project_id, user=user).project

        data = dict(title=title, assignee=assignee, description=description, status=status, priority=priority, due_date=due_date)

        def create(user, project):
            fields = _validated(TaskCreateSerializer, data, project_id=project.pk)
            return _task_record(create_task(project=project, actor=user, **fields))

        return TaskWritten(**await write(
            "create_task", idempotency_key, {"workspace": workspace_slug, "project": project_id, **data}, authorize, create,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_update_task(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, idempotency_key: UUID,
        changes: TaskChanges,
    ) -> TaskWritten:
        """Update specified task fields; due_date null clears the date. Reuse the retry key."""
        data = changes.model_dump(mode="json", exclude_unset=True)

        def update(user, task):
            fields = _validated(TaskUpdateSerializer, data, project_id=task.project_id)
            return _task_record(update_task(
                task=task, actor=user, update_due_date="due_date" in fields,
                update_assignee="assignee" in fields, **fields,
            ))

        return TaskWritten(**await write(
            "update_task", idempotency_key, {"workspace": workspace_slug, "project": project_id, "task": task_id, **data},
            lambda user: get_task_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user), update,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_move_task(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, idempotency_key: UUID,
        status: Task.Status, position: Position | None = None, before_task: UUID | None = None,
        placement: Literal["first", "last"] | None = None,
    ) -> TaskWritten:
        """Move a task on its board. Provide one of position, before_task, or placement."""
        data = {key: value for key, value in dict(status=status, position=position, before_task=before_task, placement=placement).items() if value is not None}

        def move(user, task):
            fields = _validated(TaskMoveSerializer, data)
            return _task_record(move_task(task=task, actor=user, **fields))

        return TaskWritten(**await write(
            "move_task", idempotency_key, {"workspace": workspace_slug, "project": project_id, "task": task_id, **data},
            lambda user: get_task_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user), move,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_create_task_comment(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, idempotency_key: UUID,
        body: Text, reply_to: UUID | None = None,
    ) -> CommentWritten:
        """Post a text comment or reply to an exact comment in the same task."""
        data = {"body": body, "reply_to": reply_to}

        def create(user, task):
            fields = _validated(CommentCreateSerializer, data)
            comment = create_comment(task=task, actor=user, **fields)
            return {"comment_id": comment.pk}

        return CommentWritten(**await write(
            "create_task_comment", idempotency_key, {"workspace": workspace_slug, "project": project_id, "task": task_id, **data},
            lambda user: get_comment_task_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, user=user), create,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_update_task_comment(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, comment_id: UUID,
        idempotency_key: UUID, body: Text,
    ) -> CommentWritten:
        """Edit a comment you authored in an accessible task."""
        def authorize(user):
            comment = get_comment_or_404(workspace_slug=workspace_slug, project_id=project_id, task_id=task_id, comment_id=comment_id, user=user)
            if comment.author_id != user.pk:
                raise PermissionDenied()
            return comment

        def update(user, comment):
            fields = _validated(CommentUpdateSerializer, {"body": body})
            updated = update_comment(comment=comment, actor=user, **fields)
            return {"comment_id": updated.pk}

        return CommentWritten(**await write(
            "update_task_comment", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "task": task_id, "comment": comment_id, "body": body}, authorize, update,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_send_chat_message(
        workspace_slug: WorkspaceSlug, conversation_id: UUID, idempotency_key: UUID,
        content: Text, reply_to: UUID | None = None,
    ) -> MessageWritten:
        """Send text in an existing conversation you can access."""
        def send(user, conversation):
            message = create_chat_message(
                workspace_slug=workspace_slug, conversation_id=conversation.pk, actor=user,
                content=content, reply_to=reply_to,
            )
            return {"message_id": message.pk}

        return MessageWritten(**await write(
            "send_chat_message", idempotency_key,
            {"workspace": workspace_slug, "conversation": conversation_id, "content": content, "reply_to": reply_to},
            lambda user: get_conversation_or_404(workspace_slug=workspace_slug, conversation_id=conversation_id, actor=user), send,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_start_direct_chat(
        workspace_slug: WorkspaceSlug, recipient_id: UserId, idempotency_key: UUID,
    ) -> ConversationWritten:
        """Open a direct chat with an exact active member of the same workspace."""
        def authorize(user):
            get_object_or_404(WorkspaceMembership, workspace__slug=workspace_slug, user=user)
            get_object_or_404(WorkspaceMembership, workspace__slug=workspace_slug, user_id=recipient_id, user__is_active=True)
            return get_object_or_404(get_user_model(), pk=recipient_id, is_active=True)

        def start(user, recipient):
            chat = get_or_create_direct_chat(workspace_slug=workspace_slug, recipient=recipient, actor=user)
            return {"conversation_id": chat.pk}

        return ConversationWritten(**await write(
            "start_direct_chat", idempotency_key, {"workspace": workspace_slug, "recipient": recipient_id}, authorize, start,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_mark_notification_read(notification_id: UUID, idempotency_key: UUID) -> NotificationWritten:
        """Mark one notification in your accessible inbox as read."""
        def mark(user, notice):
            visible = get_accessible_notifications(user).filter(pk=notice.pk)
            visible.filter(read_at__isnull=True).update(read_at=timezone.now())
            if not visible.filter(read_at__isnull=False).exists():
                raise Http404
            return {"notification_id": notice.pk, "is_read": True}

        return NotificationWritten(**await write(
            "mark_notification_read", idempotency_key, {"notification": notification_id},
            lambda user: get_object_or_404(get_accessible_notifications(user), pk=notification_id), mark,
        ))

    @server.tool(annotations=annotations)
    async def teamboard_mark_notifications_read(
        notification_ids: Annotated[list[UUID], Field(min_length=1, max_length=20)], idempotency_key: UUID,
    ) -> NotificationsWritten:
        """Mark up to 20 exact accessible notifications as read in one transaction."""
        ids = sorted(set(notification_ids))

        def authorize(user):
            visible = get_accessible_notifications(user).filter(pk__in=ids).order_by()
            if visible.count() != len(ids):
                raise Http404
            return visible

        def mark(user, visible):
            count = Notification.objects.filter(
                pk__in=visible.values("pk"), recipient=user, read_at__isnull=True,
            ).update(read_at=timezone.now())
            if visible.filter(read_at__isnull=False).count() != len(ids):
                raise Http404
            return {"notification_ids": ids, "updated_count": count}

        return NotificationsWritten(**await write("mark_notifications_read", idempotency_key,
            {"notifications": ids}, authorize, mark))
