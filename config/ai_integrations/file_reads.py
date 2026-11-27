from typing import Annotated
from uuid import UUID

from channels.db import database_sync_to_async
from chats.access import get_conversation_or_404
from chats.models import ChatAttachment, ChatMessage
from comments.access import get_comment_or_404
from comments.models import CommentAttachment
from django.http import Http404
from django.shortcuts import get_object_or_404
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from .tool_schema import WorkspaceSlug


class FileInfo(BaseModel):
    id: UUID
    filename: Annotated[str, Field(max_length=255)]
    size: int


class ChatFiles(BaseModel):
    attachments: list[FileInfo]


class CommentFile(BaseModel):
    attachment: FileInfo | None


def register_file_reads(server, read_only, user_id, actor):
    @database_sync_to_async
    def chat_files(account_id, slug, conversation_id, message_id):
        try:
            conversation = get_conversation_or_404(workspace_slug=slug, conversation_id=conversation_id, actor=actor(account_id))
            message = get_object_or_404(ChatMessage, pk=message_id, conversation=conversation, deleted_at__isnull=True)
        except Http404:
            raise ToolError("NOT_FOUND: Chat message unavailable.") from None
        rows = ChatAttachment.objects.filter(message=message).order_by("created_at", "id").values("id", "filename", "size")[:5]
        return ChatFiles(attachments=[FileInfo(**row) for row in rows])

    @database_sync_to_async
    def comment_file(account_id, slug, project_id, task_id, comment_id):
        try:
            comment = get_comment_or_404(workspace_slug=slug, project_id=project_id, task_id=task_id,
                comment_id=comment_id, user=actor(account_id))
        except Http404:
            raise ToolError("NOT_FOUND: Task comment unavailable.") from None
        row = CommentAttachment.objects.filter(comment=comment).values("id", "filename", "size").first()
        return CommentFile(attachment=FileInfo(**row) if row else None)

    @server.tool(annotations=read_only)
    async def teamboard_list_chat_attachments(workspace_slug: WorkspaceSlug, conversation_id: UUID, message_id: UUID) -> ChatFiles:
        """List attachment names and sizes for an exact accessible, non-deleted message."""
        return await chat_files(user_id(), workspace_slug, conversation_id, message_id)

    @server.tool(annotations=read_only)
    async def teamboard_get_task_comment_attachment(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, comment_id: UUID,
    ) -> CommentFile:
        """Inspect attachment metadata for an accessible task comment. Use TeamBoard to open files."""
        return await comment_file(user_id(), workspace_slug, project_id, task_id, comment_id)
