from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField, UserCreationForm
from django.utils.html import format_html

from .models import Profile, User, UserSession


def avatar_thumbnail(avatar):
    if not avatar:
        return '—'
    return format_html(
        '<img src="{}" alt="Profile picture" width="36" height="36" '
        'style="border-radius:50%;object-fit:cover">', avatar.url,
    )


class AdminUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class AdminUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial["password"]


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = ("first_name", "last_name", "avatar", "created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    model = User

    list_display = (
        "email",
        "avatar_preview",
        "is_email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )
    list_filter = (
        "is_email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("email",)
    ordering = ("email",)
    readonly_fields = ("date_joined", "last_login")
    inlines = (ProfileInline,)
    list_select_related = ("profile",)

    @admin.display(description="Profile picture")
    def avatar_preview(self, obj):
        return avatar_thumbnail(obj.profile.avatar)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Account Status",
            {
                "fields": (
                    "is_active",
                    "is_email_verified",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("date_joined", "last_login")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "avatar_preview", "first_name", "last_name", "created_at")
    search_fields = ("user__email", "first_name", "last_name")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user",)

    @admin.display(description="Profile picture")
    def avatar_preview(self, obj):
        return avatar_thumbnail(obj.avatar)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "is_active",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "ip_address",
    )
    list_filter = ("revoked_at", "expires_at", "created_at")
    search_fields = ("user__email", "ip_address", "user_agent")
    list_select_related = ("user",)
    readonly_fields = (
        "id",
        "user",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "ip_address",
        "user_agent",
        "refresh_token_jti",
    )
    fields = (
        "id",
        "user",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
        "ip_address",
        "user_agent",
        "refresh_token_jti",
    )

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        return obj.is_active
