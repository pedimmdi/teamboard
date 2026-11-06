
from rest_framework import serializers

from comments.models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "task",
            "author_id",
            "author_name",
            "body",
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


class CommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(
        max_length=5000,
        allow_blank=False,
        trim_whitespace=True,
    )


class CommentUpdateSerializer(CommentCreateSerializer):
    pass
