
from unittest.mock import patch

from django.test import SimpleTestCase

from chats.ws_auth import JWTWebSocketAuthMiddleware


class JWTWebSocketAuthMiddlewareTests(SimpleTestCase):
    async def test_missing_token_sets_anonymous_user(self):
        captured = {}

        async def app(scope, receive, send):
            captured["user"] = scope["user"]

        middleware = JWTWebSocketAuthMiddleware(app)

        with patch(
            "chats.ws_auth.authenticate_access_token",
            return_value=None,
        ):
            await middleware(
                {
                    "type": "websocket",
                    "subprotocols": [],
                },
                None,
                None,
            )

        self.assertIsNone(captured["user"])

    async def test_valid_token_sets_authenticated_user(self):
        captured = {}
        expected_user = object()

        async def app(scope, receive, send):
            captured["user"] = scope["user"]

        middleware = JWTWebSocketAuthMiddleware(app)

        with patch(
            "chats.ws_auth.authenticate_access_token",
            return_value=expected_user,
        ):
            await middleware(
                {
                    "type": "websocket",
                    "subprotocols": ["jwt", "example-token"],
                },
                None,
                None,
            )

        self.assertIs(
            captured["user"],
            expected_user,
        )

    async def test_unexpected_subprotocol_format_is_rejected(self):
        captured = {}

        async def app(scope, receive, send):
            captured["user"] = scope["user"]

        middleware = JWTWebSocketAuthMiddleware(app)

        with patch(
            "chats.ws_auth.authenticate_access_token",
            return_value=None,
        ) as authenticate:
            await middleware(
                {
                    "type": "websocket",
                    "subprotocols": [
                        "jwt",
                        "token",
                        "unexpected",
                    ],
                },
                None,
                None,
            )

        self.assertIsNone(captured["user"])
        authenticate.assert_awaited_once_with(None)
