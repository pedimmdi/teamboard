from django.contrib import admin

from .models import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
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


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "user",
        "role",
        "joined_at",
    )
    list_filter = ("role", "joined_at")
    search_fields = (
        "organization__name",
        "organization__slug",
        "user__email",
    )
    ordering = ("joined_at",)
    list_select_related = ("organization", "user")
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("id", "joined_at")


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organization",
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
        "organization__name",
        "organization__slug",
        "invited_by__email",
    )
    ordering = ("-created_at", "-id")
    list_select_related = ("organization", "invited_by")
    date_hierarchy = "created_at"

    readonly_fields = (
        "id",
        "organization",
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
