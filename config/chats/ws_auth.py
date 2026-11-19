
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.authentication import SessionJWTAuthentication


@database_sync_to_async
def authenticate_access_token(raw_token):
    if not raw_token:
        return AnonymousUser()

    try:
        factory = APIRequestFactory()

        request = Request(
            factory.get(
                "/",
                HTTP_AUTHORIZATION=f"Bearer {raw_token}",
            )
        )

        authentication = SessionJWTAuthentication()
        result = authentication.authenticate(request)

        if result is None:
            return AnonymousUser()

        user, _ = result
        return user

    except (AuthenticationFailed, InvalidToken, TokenError):
        return AnonymousUser()


class JWTWebSocketAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope = dict(scope)

        protocols = scope.get("subprotocols", [])

        token = None

        if (
            len(protocols) == 2
            and protocols[0] == "jwt"
        ):
            token = protocols[1]

        scope["user"] = await authenticate_access_token(token)

        return await self.app(scope, receive, send)
