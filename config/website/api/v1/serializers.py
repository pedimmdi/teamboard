from rest_framework import serializers

from website.models import BlogPost


class ContactMessageSubmitSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=120,
        trim_whitespace=True,
    )

    email = serializers.EmailField(
        max_length=254,
    )

    subject = serializers.CharField(
        max_length=180,
        trim_whitespace=True,
    )

    message = serializers.CharField(
        max_length=5000,
        trim_whitespace=True,
    )

    # Optional spam trap. Real visitors leave it empty.
    website_url = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        trim_whitespace=True,
        write_only=True,
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        for field in ("name", "subject", "message"):
            if "\x00" in attrs[field]:
                raise serializers.ValidationError({
                    field: "Null characters are not allowed."
                })

        for field in ("name", "subject"):
            if "\r" in attrs[field] or "\n" in attrs[field]:
                raise serializers.ValidationError({
                    field: "Line breaks are not allowed."
                })

        return attrs


class ContactMessageSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


class PublicBlogPostSerializer(serializers.ModelSerializer):
    has_persian_translation = serializers.BooleanField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.query_params.get("lang") == "fa" and instance.has_persian_translation:
            data["title"] = instance.title_fa
            data["excerpt"] = instance.excerpt_fa
            if "content" in data:
                data["content"] = instance.content_fa
        return data


class PublicBlogPostListSerializer(PublicBlogPostSerializer):
    """
    A lightweight article representation for blog listings.
    """

    class Meta:
        model = BlogPost

        fields = (
            "id",
            "title",
            "slug",
            "excerpt",
            "published_at",
            "updated_at",
            "has_persian_translation",
        )

        read_only_fields = fields


class PublicBlogPostDetailSerializer(PublicBlogPostSerializer):
    """
    Public article details, including Markdown content.
    """

    class Meta:
        model = BlogPost

        fields = (
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "published_at",
            "updated_at",
            "has_persian_translation",
        )

        read_only_fields = fields
