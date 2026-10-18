from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    password_validation,
)
from django.contrib.auth.tokens import (
    PasswordResetTokenGenerator,
    default_token_generator,
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User, UserSession

User = get_user_model()


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    verification_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/verify-email/"
        f"?uid={uid}&token={token}"
    )

    message = (
        "Hello,\n\n"
        "Welcome to TeamBoard.\n\n"
        "Please verify your email address by opening the following link:\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    send_mail(
        subject="Verify your TeamBoard email address",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[password_validation.validate_password],
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = ("email", "password", "password_confirm")

    def validate_email(self, value):
        value = User.objects.normalize_email(value)

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")

        try:
            with transaction.atomic():
                user = User.objects.create_user(**validated_data)

                transaction.on_commit(
                    lambda: send_verification_email(user),
                    robust=True,
                )
        except IntegrityError:
            raise serializers.ValidationError({
                "email": "A user with this email already exists."
            })

        return user


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        request = self.context.get("request")

        user = authenticate(
            request=request,
            **{
                User.USERNAME_FIELD: attrs.get(User.USERNAME_FIELD),
                "password": attrs.get("password"),
            },
        )

        if user is None:
            raise AuthenticationFailed(
                "No active account found with the given credentials."
            )

        if not user.is_email_verified:
            raise PermissionDenied("Email address is not verified.")

        with transaction.atomic():
            refresh = RefreshToken.for_user(user)

            session = UserSession.objects.create(
                user=user,
                expires_at=datetime.fromtimestamp(
                    refresh["exp"],
                    tz=dt_timezone.utc,
                ),
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:512]
                if request
                else "",
                refresh_token_jti=str(refresh["jti"]),
            )

            refresh["session_id"] = str(session.id)

            access = refresh.access_token

        return {
            "refresh": str(refresh),
            "access": str(access),
        }

    def _get_client_ip(self, request):
        if request is None:
            return None

        return request.META.get("REMOTE_ADDR")


class SessionRefreshTokenSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        session_id = refresh.get("session_id")

        if not session_id:
            raise AuthenticationFailed("Session is no longer valid.")

        try:
            session = UserSession.objects.get(
                id=session_id,
                user_id=refresh.get("user_id"),
            )
        except UserSession.DoesNotExist:
            raise AuthenticationFailed("Session is no longer valid.")

        if (
            not session.is_active
            or session.refresh_token_jti != str(refresh["jti"])
        ):
            raise AuthenticationFailed("Session is no longer valid.")

        with transaction.atomic():
            data = super().validate(attrs)

            session.last_seen_at = timezone.now()
            session.save(update_fields=["last_seen_at"])

        return data


class CurrentUserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        source="profile.first_name",
        required=False,
        allow_blank=True,
        max_length=150,
    )
    last_name = serializers.CharField(
        source="profile.last_name",
        required=False,
        allow_blank=True,
        max_length=150,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "date_joined",
            "is_email_verified",
        )
        read_only_fields = ("id", "email", "date_joined", "is_email_verified")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})

        for field, value in profile_data.items():
            setattr(instance.profile, field, value)

        if profile_data:
            instance.profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(
                "Current password is incorrect."
            )
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        user = self.context["request"].user

        if user.check_password(attrs["new_password"]):
            raise serializers.ValidationError(
                {"new_password": "Choose a different password."}
            )

        try:
            password_validation.validate_password(
                attrs["new_password"],
                user=user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"new_password": list(exc.messages)}
            )

        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Invalid or revoked refresh token."}
            )

        request = self.context["request"]

        if str(token["user_id"]) != str(request.user.pk):
            raise serializers.ValidationError(
                {"refresh": "This token does not belong to this user."}
            )

        attrs["token"] = token
        return attrs

    def save(self, **kwargs):
        token = self.validated_data["token"]
        request = self.context["request"]

        token.blacklist()

        session_id = token.get("session_id")

        if session_id:
            session = UserSession.objects.filter(
                id=session_id,
                user=request.user,
            ).first()

            if session and session.revoked_at is None:
                session.revoked_at = timezone.now()
                session.save(update_fields=["revoked_at"])

        return token


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        email = self.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user is None:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)

        reset_url = (
            f"{settings.FRONTEND_URL.rstrip('/')}"
            f"/reset-password/?uid={uid}&token={token}"
        )

        message = (
            "Hello,\n\n"
            "You requested a password reset for your TeamBoard account.\n"
            f"Use this link to choose a new password:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )

        transaction.on_commit(
            lambda: send_mail(
                subject="Reset your TeamBoard password",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            ),
            robust=True,
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Passwords do not match."
            })

        try:
            user_id = force_str(
                urlsafe_base64_decode(attrs["uid"])
            )
            user = User.objects.get(pk=user_id, is_active=True)
        except (
            ValueError,
            TypeError,
            OverflowError,
            DjangoValidationError,
            User.DoesNotExist,
        ):
            raise serializers.ValidationError({
                "uid": "Invalid password reset link."
            })

        if not PasswordResetTokenGenerator().check_token(
            user,
            attrs["token"],
        ):
            raise serializers.ValidationError({
                "token": "Invalid or expired password reset link."
            })

        if user.check_password(attrs["new_password"]):
            raise serializers.ValidationError({
                "new_password": "Choose a different password."
            })

        try:
            password_validation.validate_password(
                attrs["new_password"],
                user=user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "new_password": list(exc.messages)
            })

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class EmailVerificationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (
            ValueError,
            TypeError,
            OverflowError,
            DjangoValidationError,
            User.DoesNotExist,
        ):
            raise serializers.ValidationError(
                {"uid": "Invalid verification link."}
            )

        if user.is_email_verified:
            raise serializers.ValidationError(
                {"detail": "Email address is already verified."}
            )

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Invalid or expired verification link."}
            )

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return user


class ResendVerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        email = self.validated_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
            is_email_verified=False,
        ).first()

        if user is None:
            return

        transaction.on_commit(
            lambda: send_verification_email(user),
            robust=True,
        )


class UserSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = (
            "id",
            "created_at",
            "last_seen_at",
            "expires_at",
            "ip_address",
            "user_agent",
            "is_active",
            "is_current",
        )
        read_only_fields = fields

    def get_is_current(self, obj) -> bool:
        current_session_id = self.context.get("current_session_id")
        return str(obj.id) == str(current_session_id)
