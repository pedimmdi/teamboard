from django.contrib import admin

from .models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceInvitation,
)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "slug")
    ordering = ("name",)
    readonly_fields = (
        "id",
        "slug",
        "created_at",
        "updated_at",
    )


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "user",
        "role",
        "joined_at",
    )
    list_filter = ("role", "joined_at")
    search_fields = (
        "workspace__name",
        "workspace__slug",
        "user__email",
    )
    ordering = ("joined_at",)
    list_select_related = ("workspace", "user")
    autocomplete_fields = ("workspace", "user")
    readonly_fields = ("id", "joined_at")


@admin.register(WorkspaceInvitation)
class WorkspaceInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "workspace",
        "status",
        "invited_by",
        "created_at",
        "expires_at",
    )
    list_filter = (
        "status",
        "created_at",
        "expires_at",
    )
    search_fields = (
        "email",
        "workspace__name",
        "workspace__slug",
        "invited_by__email",
    )
    ordering = ("-created_at", "-id")
    list_select_related = ("workspace", "invited_by")
    date_hierarchy = "created_at"

    readonly_fields = (
        "id",
        "workspace",
        "email",
        "invited_by",
        "token_hash",
        "status",
        "created_at",
        "expires_at",
        "accepted_at",
        "revoked_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)
