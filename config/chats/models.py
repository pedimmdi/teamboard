
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, F


class Conversation(models.Model):
    class Type(models.TextChoices):
        PROJECT = "project", "Project"
        DIRECT = "direct", "Direct"

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    type = models.CharField(max_length=10, choices=Type.choices)
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conversation",
    )
    direct_user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    direct_user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        type="project",
                        project__isnull=False,
                        direct_user_low__isnull=True,
                        direct_user_high__isnull=True,
                    )
                    | Q(
                        type="direct",
                        project__isnull=True,
                        direct_user_low__isnull=False,
                        direct_user_high__isnull=False,
                    )
                ),
                name="chat_valid_conversation_type",
            ),
            models.CheckConstraint(
                condition=(
                    Q(direct_user_low__isnull=True)
                    | Q(direct_user_high__isnull=True)
                    | Q(direct_user_low__lt=F("direct_user_high"))
                ),
                name="chat_direct_user_order",
            ),
            models.UniqueConstraint(
                fields=[
                    "workspace",
                    "direct_user_low",
                    "direct_user_high",
                ],
                condition=Q(type="direct"),
                name="chat_unique_direct_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["workspace", "type", "-updated_at"],
                name="chat_ws_type_updated_idx",
            ),
        ]


class ConversationParticipant(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_participations",
    )
    last_read_message = models.ForeignKey(
        "ChatMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Durable ordered cursor, retained even if an administrator hard-deletes
    # last_read_message. Normal message deletion is a soft delete.
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_key = models.UUIDField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="chat_unique_participant",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "conversation"],
                name="chat_participant_user_idx",
            ),
        ]


class ChatMessage(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )
    content = models.TextField(blank=True, max_length=5000)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at", "id"],
                name="chat_message_date_idx",
            ),
        ]


class ChatAttachment(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(size__gt=0),
                name="chat_attachment_size_positive",
            ),
        ]
