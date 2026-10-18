from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from accounts.models import UserSession
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from .serializers import (
    LoginSerializer,
    SessionRefreshTokenSerializer,
    ChangePasswordSerializer,
    CurrentUserSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    EmailVerificationSerializer,
    ResendVerificationEmailSerializer,
    UserSessionSerializer,
)
from django.contrib.auth import get_user_model

User = get_user_model()


def invalidate_user_sessions(user):
    now = timezone.now()

    UserSession.objects.filter(
        user=user,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(
            {"detail": "Registration successful."},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshTokenView(TokenRefreshView):
    serializer_class = SessionRefreshTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.select_related("profile")

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    @extend_schema(
        summary="Change password",
        description=(
            "Changes the authenticated user's password. "
            "Existing sessions are invalidated after a successful change."
        ),
        request=ChangePasswordSerializer,
        responses={
            200: inline_serializer(
                name="ChangePasswordResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid request data or current password."
            ),
            401: OpenApiResponse(
                description="Authentication credentials are missing or invalid."
            ),
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = request.user

        with transaction.atomic():
            serializer.save()
            invalidate_user_sessions(user)

        return Response(
            {
                "detail": "Password changed successfully. Please log in again."
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "logout"

    @extend_schema(
        summary="Log out",
        description="Logs out the authenticated session.",
        request=LogoutSerializer,
        responses={
            200: inline_serializer(
                name="LogoutResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid logout request."
            ),
            401: OpenApiResponse(
                description="Authentication credentials are missing or invalid."
            ),
        },
    )
    def post(self, request):
        serializer = LogoutSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            serializer.save()

        return Response(
            {"detail": "Logout successful."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Request password reset",
        description=(
            "Requests password reset instructions. "
            "The response does not reveal whether the email exists."
        ),
        request=PasswordResetRequestSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetRequestResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid request data."
            ),
            429: OpenApiResponse(
                description="Too many requests."
            ),
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "detail": (
                    "If an account exists for this email, "
                    "password reset instructions have been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        summary="Confirm password reset",
        description=(
            "Resets the password using a valid password-reset token "
            "and invalidates the user's existing sessions."
        ),
        request=PasswordResetConfirmSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetConfirmResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid, expired, or incomplete reset data."
            ),
            429: OpenApiResponse(
                description="Too many requests."
            ),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        with transaction.atomic():
            serializer.save()
            invalidate_user_sessions(user)

        return Response(
            {
                "detail": "Password has been reset successfully."
            },
            status=status.HTTP_200_OK,
        )


class EmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    @extend_schema(
        summary="Verify email address",
        description="Verifies an email address using the supplied verification token.",
        parameters=[
            OpenApiParameter(
                name="uid",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Encoded user identifier.",
            ),
            OpenApiParameter(
                name="token",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Email verification token.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="EmailVerificationResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid or expired verification data."
            ),
            429: OpenApiResponse(
                description="Too many requests."
            ),
        },
    )
    def get(self, request):
        serializer = EmailVerificationSerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"detail": "Email address verified successfully."},
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_resend"

    @extend_schema(
        summary="Resend email verification",
        description=(
            "Requests a new verification email without revealing "
            "whether the email address is registered or already verified."
        ),
        request=ResendVerificationEmailSerializer,
        responses={
            200: inline_serializer(
                name="ResendVerificationEmailResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="Invalid request data."
            ),
            429: OpenApiResponse(
                description="Too many requests."
            ),
        },
    )
    def post(self, request):
        serializer = ResendVerificationEmailSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "detail": (
                    "If the email address requires verification, "
                    "a verification email has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class SessionListView(generics.ListAPIView):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.select_related("user").filter(
            user=self.request.user,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).order_by("-last_seen_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["current_session_id"] = self.request.auth.get(
            "session_id"
        )
        return context


class SessionRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Revoke a session",
        description="Revokes a session belonging to the authenticated user.",
        parameters=[
            OpenApiParameter(
                name="session_id",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="ID of the session to revoke.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="SessionRevokeResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
            401: OpenApiResponse(
                description="Authentication credentials are missing or invalid."
            ),
            404: OpenApiResponse(
                description="The session does not exist or does not belong to the user."
            ),
        },
    )
    @transaction.atomic
    def delete(self, request, session_id):
        session = UserSession.objects.filter(
            id=session_id,
            user=request.user,
        ).first()

        if session is None:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        self._revoke_session(session)

        return Response(
            {"detail": "Session revoked successfully."},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _revoke_session(session):
        if session.revoked_at is None:
            session.revoked_at = timezone.now()
            session.save(update_fields=["revoked_at"])

        outstanding_token = OutstandingToken.objects.filter(
            jti=session.refresh_token_jti,
            user=session.user,
        ).first()

        if outstanding_token is not None:
            BlacklistedToken.objects.get_or_create(
                token=outstanding_token
            )


class RevokeOtherSessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Revoke other sessions",
        description=(
            "Revokes the authenticated user's other active sessions "
            "while keeping the current session active."
        ),
        request=None,
        responses={
            200: inline_serializer(
                name="RevokeOtherSessionsResponse",
                fields={
                    "detail": serializers.CharField(),
                    "revoked_count": serializers.IntegerField(),
                },
            ),
            400: OpenApiResponse(
                description="The current token is not associated with a session."
            ),
            401: OpenApiResponse(
                description="Authentication credentials are missing or invalid."
            ),
        },
    )
    @transaction.atomic
    def post(self, request):
        current_session_id = request.auth.get("session_id")

        if not current_session_id:
            raise ValidationError(
                "The current token is not associated with a session."
            )

        other_sessions = UserSession.objects.filter(
            user=request.user,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        ).exclude(id=current_session_id)

        revoked_count = 0

        for session in other_sessions:
            SessionRevokeView._revoke_session(session)
            revoked_count += 1

        return Response(
            {
                "detail": "Other sessions revoked successfully.",
                "revoked_count": revoked_count,
            },
            status=status.HTTP_200_OK,
        )
