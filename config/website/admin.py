
from django.contrib import admin

from website.models import BlogPost, ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """
    Private contact inbox.

    Administrators may review and update the status,
    but must not modify the original submission.
    """

    list_display = (
        "subject",
        "name",
        "email",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "subject",
        "name",
        "email",
        "message",
    )

    ordering = ("-created_at", "-id")

    readonly_fields = (
        "id",
        "name",
        "email",
        "subject",
        "message",
        "created_at",
        "updated_at",
    )

    fields = (
        "id",
        "name",
        "email",
        "subject",
        "message",
        "status",
        "created_at",
        "updated_at",
    )

    list_per_page = 25
    show_full_result_count = False

    # Do not allow accidental bulk deletion.
    actions = None

    def has_add_permission(self, request):
        # Messages must originate from the public Contact API.
        return False

    def has_delete_permission(self, request, obj=None):
        # Retain the original submission while it is reviewed.
        return False


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """
    Editorial administration for public blog content.

    Only published posts with published_at <= now
    are exposed by the separate public Blog API.
    """

    list_display = (
        "title",
        "slug",
        "status",
        "published_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "published_at",
        "created_at",
    )

    search_fields = (
        "title",
        "slug",
        "excerpt",
    )

    ordering = ("-created_at", "-id")

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    fields = (
        "id",
        "title",
        "slug",
        "excerpt",
        "content",
        "status",
        "published_at",
        "created_at",
        "updated_at",
    )

    list_per_page = 25
    show_full_result_count = False

    date_hierarchy = "created_at"
