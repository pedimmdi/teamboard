
from django.contrib import admin

from projects.models import Project, ProjectMembership


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    can_delete = False
    fields = ("user", "role", "joined_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "created_by",
        "created_at",
    )
    list_filter = ("workspace", "created_at")
    search_fields = (
        "name",
        "workspace__name",
        "created_by__email",
    )
    readonly_fields = (
        "id",
        "workspace",
        "created_by",
        "created_at",
        "updated_at",
    )
    fields = (
        "id",
        "name",
        "description",
        "workspace",
        "created_by",
        "created_at",
        "updated_at",
    )
    inlines = [ProjectMembershipInline]
    list_select_related = ("workspace", "created_by")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        return self.readonly_fields + ("name", "description")

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "project",
        "role",
        "joined_at",
    )
    list_filter = ("role",)
    search_fields = (
        "user__email",
        "project__name",
        "project__workspace__name",
    )
    readonly_fields = (
        "id",
        "user",
        "project",
        "role",
        "joined_at",
    )
    list_select_related = ("user", "project")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff
