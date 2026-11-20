from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from chats.models import ChatMessage, Conversation


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id",
            "workspace",
            "type",
            "project",
            "direct_user_low",
            "direct_user_high",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DirectCreateSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField(min_value=1)


class ChatAttachmentMetadataSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    filename = serializers.CharField(read_only=True)
    size = serializers.IntegerField(read_only=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    reply_to = serializers.UUIDField(source="reply_to_id", read_only=True, allow_null=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "conversation",
            "sender_id",
            "content",
            "reply_to",
            "attachments",
            "created_at",
            "edited_at",
            "deleted_at",
        ]
        read_only_fields = fields

    @extend_schema_field(
        ChatAttachmentMetadataSerializer(many=True)
    )
    def get_attachments(self, obj):
        if obj.deleted_at is not None:
            return []

        return [
            {
                "id": str(attachment.id),
                "filename": attachment.filename,
                "size": attachment.size,
            }
            for attachment in obj.attachments.all()
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.deleted_at is not None:
            data["content"] = ""
        return data


class ChatMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=5000,
        trim_whitespace=True,
        allow_blank=True,
        required=False,
        default="",
    )
    reply_to = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    attachments = serializers.ListField(
        child=serializers.FileField(
            allow_empty_file=False,
        ),
        required=False,
        allow_empty=True,
        max_length=5,
        write_only=True,
    )


class ChatMessageUpdateSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=5000,
        trim_whitespace=True,
        allow_blank=True,
    )


class ChatUnreadConversationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    project = serializers.UUIDField(allow_null=True)
    recipient_id = serializers.IntegerField(allow_null=True)
    unread_count = serializers.IntegerField(min_value=0)


class ChatUnreadSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField(min_value=0)
    conversations = ChatUnreadConversationSerializer(many=True)


class ChatReadSerializer(serializers.Serializer):
    message_id = serializers.UUIDField()
