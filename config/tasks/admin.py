
from django.contrib import admin

from tasks.models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project",
        "workspace_name",
        "status",
        "priority",
        "assignee",
        "created_by",
        "due_date",
        "created_at",
    )

    list_filter = (
        "status",
        "priority",
        "project__workspace",
        "created_at",
        "due_date",
    )

    search_fields = (
        "title",
        "description",
        "project__name",
        "project__workspace__name",
        "assignee__email",
        "created_by__email",
    )

    readonly_fields = (
        "id",
        "project",
        "title",
        "description",
        "status",
        "priority",
        "assignee",
        "created_by",
        "due_date",
        "created_at",
        "updated_at",
    )

    fields = (
        "id",
        "project",
        "title",
        "description",
        "status",
        "priority",
        "assignee",
        "created_by",
        "due_date",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "project__workspace",
        "assignee",
        "created_by",
    )

    ordering = ("-created_at", "-pk")
    list_per_page = 25
    show_full_result_count = False

    @admin.display(description="Workspace")
    def workspace_name(self, obj):
        return obj.project.workspace.name

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        )
