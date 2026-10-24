from django.contrib import admin

from .models import Organization, OrganizationMembership


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
