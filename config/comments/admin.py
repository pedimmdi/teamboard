
from django.contrib import admin

from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "author",
        "body_preview",
        "created_at",
        "updated_at",
    )

    list_display_links = ("id", "body_preview")

    list_filter = (
        "created_at",
        "updated_at",
    )

    search_fields = (
        "=id",
        "body",
        "task__title",
        "author__email",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "task",
        "author",
    )

    list_select_related = (
        "task",
        "author",
    )

    ordering = ("-created_at", "-id")

    list_per_page = 25

    @admin.display(description="Comment")
    def body_preview(self, obj):
        if len(obj.body) > 80:
            return f"{obj.body[:80]}..."
        return obj.body
