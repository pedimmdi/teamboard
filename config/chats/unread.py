"""Unread messages share exactly the access rules of conversation retrieval."""
from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404

from chats.access import get_chat_workspace, get_conversation_or_404
from chats.models import ChatMessage, Conversation, ConversationParticipant
from projects.access import get_accessible_workspace_project_ids


def get_unread_chats(*, workspace_slug, actor):
    workspace = get_chat_workspace(workspace_slug=workspace_slug, actor=actor)
    projects = get_accessible_workspace_project_ids(workspace_slug=workspace_slug, user=actor)
    accessible = Conversation.objects.filter(workspace=workspace).filter(
        Q(type="project", project_id__in=projects)
        | Q(type="direct", direct_user_low=actor)
        | Q(type="direct", direct_user_high=actor)
    )
    cursor = ConversationParticipant.objects.filter(conversation_id=OuterRef("conversation_id"), user=actor)
    rows = (
        ChatMessage.objects.filter(conversation__in=accessible, deleted_at__isnull=True)
        .exclude(sender=actor)
        .annotate(read_at=Subquery(cursor.values("last_read_at")[:1]), read_key=Subquery(cursor.values("last_read_key")[:1]))
        .filter(Q(read_at__isnull=True) | Q(created_at__gt=F("read_at")) | Q(created_at=F("read_at"), id__gt=F("read_key")))
        .order_by()
        .values("conversation_id", "conversation__project_id", "conversation__type", "conversation__direct_user_low_id", "conversation__direct_user_high_id")
        .annotate(unread_count=Count("id"))
    )
    conversations = [
        {
            "id": row["conversation_id"], "project": row["conversation__project_id"],
            "recipient_id": (row["conversation__direct_user_high_id"] if row["conversation__direct_user_low_id"] == actor.pk else row["conversation__direct_user_low_id"]) if row["conversation__type"] == "direct" else None,
            "unread_count": row["unread_count"],
        }
        for row in rows
    ]
    return {"unread_count": sum(row["unread_count"] for row in conversations), "conversations": conversations}


@transaction.atomic
def mark_chat_read(*, workspace_slug, conversation_id, actor, message_id):
    conversation = get_conversation_or_404(workspace_slug=workspace_slug, conversation_id=conversation_id, actor=actor)
    message = get_object_or_404(ChatMessage, pk=message_id, conversation=conversation)
    # get_or_create handles the first-read race; locking serializes subsequent
    # acknowledgements so an older browser cannot move the cursor backwards.
    participant, _ = ConversationParticipant.objects.get_or_create(conversation=conversation, user=actor)
    participant = ConversationParticipant.objects.select_for_update().get(pk=participant.pk)
    if participant.last_read_at is None or (message.created_at, message.pk) > (participant.last_read_at, participant.last_read_key):
        participant.last_read_message = message
        participant.last_read_at = message.created_at
        participant.last_read_key = message.pk
        participant.save(update_fields=["last_read_message", "last_read_at", "last_read_key"])
