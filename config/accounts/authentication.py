from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import UserSession


class SessionJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            return None

        user, validated_token = result
        session_id = validated_token.get("session_id")

        if not session_id:
            raise AuthenticationFailed("Session is no longer valid.")

        try:
            session = UserSession.objects.select_related("user").get(
                id=session_id,
                user=user,
            )
        except UserSession.DoesNotExist:
            raise AuthenticationFailed("Session is no longer valid.")

        if not session.is_active:
            raise AuthenticationFailed("Session is no longer valid.")

        return user, validated_token
