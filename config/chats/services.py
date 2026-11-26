import logging
from pathlib import Path
from uuid import uuid4

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from projects.models import Project
from workspaces.models import Workspace

from .access import (
    ensure_direct_recipient,
    get_chat_workspace,
    get_project_chat_access,
    get_conversation_or_404,
)
from .models import (
    ChatAttachment,
    ChatMessage,
    Conversation,
    ConversationParticipant,
)
from .storage import (
    chat_attachment_storage,
    validate_chat_attachments,
)
from .events import schedule_chat_event
from chats.attachment_cleanup import cleanup_deleted_attachment

logger = logging.getLogger(__name__)


def cleanup_deleted_message_attachments(message_id):
    attachment_ids = list(
        ChatAttachment.objects.filter(
            message_id=message_id,
            message__deleted_at__isnull=False,
        ).values_list("pk", flat=True)
    )

    for attachment_id in attachment_ids:
        try:
            cleanup_deleted_attachment(attachment_id)
        except Exception:
            logger.exception(
                "Failed to clean chat attachment: %s",
                attachment_id,
            )


@transaction.atomic
def get_or_create_project_chat(
    *, workspace_slug, project_id, actor
):
    project = get_project_chat_access(
        workspace_slug=workspace_slug,
        project_id=project_id,
        actor=actor,
    )

    # Lock the parent project so concurrent requests cannot
    # initialize separate conversations for the same project.
    project = get_object_or_404(
        Project.objects.select_for_update(),
        pk=project.pk,
        workspace__slug=workspace_slug,
    )

    conversation, _ = Conversation.objects.get_or_create(
        project=project,
        defaults={
            "workspace": project.workspace,
            "type": Conversation.Type.PROJECT,
        },
    )
    return conversation


@transaction.atomic
def get_or_create_direct_chat(
    *, workspace_slug, recipient, actor
):
    workspace = get_chat_workspace(
        workspace_slug=workspace_slug,
        actor=actor,
    )

    # Serialize creation within the same workspace.
    workspace = get_object_or_404(
        Workspace.objects.select_for_update(),
        pk=workspace.pk,
    )

    # Recheck both memberships while holding the workspace lock.
    get_chat_workspace(
        workspace_slug=workspace_slug,
        actor=actor,
    )
    ensure_direct_recipient(
        workspace=workspace,
        recipient=recipient,
        actor=actor,
    )

    low_id, high_id = sorted((actor.pk, recipient.pk))

    conversation, created = Conversation.objects.get_or_create(
        workspace=workspace,
        type=Conversation.Type.DIRECT,
        direct_user_low_id=low_id,
        direct_user_high_id=high_id,
    )

    if created:
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(
                conversation=conversation,
                user_id=low_id,
            ),
            ConversationParticipant(
                conversation=conversation,
                user_id=high_id,
            ),
        ])

    return conversation


MAX_MESSAGE_LENGTH = 5000


def validate_message_content(content, *, allow_empty=False):
    if not isinstance(content, str):
        raise ValidationError({
            "content": "Message content must be a string.",
        })

    content = content.strip()

    if not content and not allow_empty:
        raise ValidationError({
            "content": "Message cannot be empty.",
        })

    if len(content) > MAX_MESSAGE_LENGTH:
        raise ValidationError({
            "content": "Message cannot exceed 5000 characters.",
        })

    return content


@transaction.atomic
def create_chat_message(
    *,
    workspace_slug,
    conversation_id,
    actor,
    content,
    reply_to=None,
    attachments=None,
):
    conversation = get_conversation_or_404(
        workspace_slug=workspace_slug,
        conversation_id=conversation_id,
        actor=actor,
    )

    files = validate_chat_attachments(attachments or [])
    content = validate_message_content(
        content,
        allow_empty=bool(files),
    )

    parent = None
    if reply_to is not None:
        parent = ChatMessage.objects.filter(
            pk=reply_to,
            conversation=conversation,
            deleted_at__isnull=True,
        ).first()

        if parent is None:
            raise ValidationError({
                "reply_to": "Choose an existing message in this conversation.",
            })

    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=actor,
        content=content,
        reply_to=parent,
    )

    storage = chat_attachment_storage()
    saved_keys = []

    try:
        for file in files:
            storage_key = storage.save(
                f"uploads/{uuid4().hex}",
                file,
            )
            saved_keys.append(storage_key)

            ChatAttachment.objects.create(
                message=message,
                filename=Path(file.name).name[:255],
                size=file.size,
                content_type=(
                    "image/png"
                    if Path(file.name).suffix.lower() == ".png"
                    else "image/jpeg"
                    if Path(file.name).suffix.lower() in (".jpg", ".jpeg")
                    else "text/plain"
                ),
                storage_key=storage_key,
            )

        Conversation.objects.filter(
            pk=conversation.pk,
        ).update(updated_at=timezone.now())

    except Exception:
        for key in saved_keys:
            try:
                storage.delete(key)
            except Exception:
                logger.exception(
                    "Failed to clean up chat attachment: %s",
                    key,
                )
        raise

    schedule_chat_event(
        conversation_id=conversation.pk,
        event_type="message.created",
        message_id=message.pk,
    )

    return message


@transaction.atomic
def update_chat_message(
    *, workspace_slug, message_id, actor, content
):
    message = get_object_or_404(
        ChatMessage.objects.select_for_update(),
        pk=message_id,
    )

    get_conversation_or_404(
        workspace_slug=workspace_slug,
        conversation_id=message.conversation_id,
        actor=actor,
    )

    if message.sender_id != actor.pk:
        raise PermissionDenied(
            "Only the sender can edit this message."
        )

    if message.deleted_at is not None:
        raise ValidationError({
            "detail": "Deleted messages cannot be edited.",
        })

    message.content = validate_message_content(content)
    message.edited_at = timezone.now()
    message.save(update_fields=["content", "edited_at"])

    schedule_chat_event(
        conversation_id=message.conversation_id,
        event_type="message.updated",
        message_id=message.pk,
    )

    return message


@transaction.atomic
def delete_chat_message(
    *, workspace_slug, message_id, actor
):
    message = get_object_or_404(
        ChatMessage.objects.select_for_update(),
        pk=message_id,
    )

    get_conversation_or_404(
        workspace_slug=workspace_slug,
        conversation_id=message.conversation_id,
        actor=actor,
    )

    if message.sender_id != actor.pk:
        raise PermissionDenied(
            "Only the sender can delete this message."
        )

    if message.deleted_at is not None:
        return message

    message.content = ""
    message.deleted_at = timezone.now()
    message.save(
        update_fields=["content", "deleted_at"]
    )

    from background.services import enqueue_chat_attachments
    enqueue_chat_attachments(message.pk)

    schedule_chat_event(
        conversation_id=message.conversation_id,
        event_type="message.deleted",
        message_id=message.pk,
    )

    return message


def message_response_queryset():
    attachments = ChatAttachment.objects.only("id", "message_id", "filename", "size")
    return ChatMessage.objects.prefetch_related(Prefetch("attachments", queryset=attachments))


def get_chat_messages(
    *, workspace_slug, conversation_id, actor
):
    conversation = get_conversation_or_404(
        workspace_slug=workspace_slug,
        conversation_id=conversation_id,
        actor=actor,
    )

    return (
        message_response_queryset()
        .filter(conversation=conversation)
        .order_by("-created_at", "-id")
    )
