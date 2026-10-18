from django.urls import path

from .views import (
    ChangePasswordView,
    CurrentUserView,
    EmailVerificationView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshTokenView,
    RegisterView,
    ResendVerificationEmailView,
    SessionListView,
    SessionRevokeView,
    RevokeOtherSessionsView,
)

app_name = "accounts_api_v1"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path(
        "sessions/",
        SessionListView.as_view(),
        name="session_list",
    ),
    path(
        "sessions/revoke-others/",
        RevokeOtherSessionsView.as_view(),
        name="session_revoke_others",
    ),
    path(
        "sessions/<uuid:session_id>/",
        SessionRevokeView.as_view(),
        name="session_revoke",
    ),
    path("password/change/", ChangePasswordView.as_view(), name="password_change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "email/verify/",
        EmailVerificationView.as_view(),
        name="email_verify",
    ),
    path(
        "email/resend/",
        ResendVerificationEmailView.as_view(),
        name="email_resend",
    ),
]
