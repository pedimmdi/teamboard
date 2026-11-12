
from rest_framework import serializers

from drf_spectacular.utils import extend_schema_field

from comments.models import Comment


class AttachmentMetadataSerializer(serializers.Serializer):
    filename = serializers.CharField()
    size = serializers.IntegerField()


class CommentSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    author_name = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()
    mentions = serializers.SlugRelatedField(many=True, read_only=True, slug_field="email")

    @extend_schema_field(AttachmentMetadataSerializer(allow_null=True))
    def get_attachment(self, obj):
        attachment = getattr(obj, "attachment", None)
        return AttachmentMetadataSerializer(attachment).data if attachment else None

    class Meta:
        model = Comment
        fields = [
            "id",
            "task",
            "author_id",
            "author_name",
            "body",
            "reply_to",
            "mentions",
            "attachment",
            "edited_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_author_name(self, obj) -> str:
        if obj.author_id is None:
            return "Deleted user"

        profile = getattr(obj.author, "profile", None)

        if profile:
            name = profile.full_name
            if name:
                return name

        return obj.author.email


class CommentUpdateSerializer(serializers.Serializer):
    body = serializers.CharField(
        max_length=5000,
        allow_blank=True,
        trim_whitespace=True,
    )


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, allow_blank=True, default="")
    reply_to = serializers.UUIDField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, max_length=255)

    def validate(self, attrs):
        if not attrs["body"] and "attachment" not in attrs:
            raise serializers.ValidationError({"body": "Comment cannot be empty."})
        return attrs
