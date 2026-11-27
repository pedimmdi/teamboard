import asyncio
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from channels.testing import WebsocketCommunicator
from chats.models import Conversation
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TransactionTestCase
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_refresh_token_model,
)
from workspaces.models import Workspace, WorkspaceMembership

from ai_integrations.oauth import BROWSER_COOKIE
from ai_integrations.tests.http import mcp_test_client
from config import mcp_local_asgi

CALLBACK = "http://127.0.0.1:6274/callback"
PASSWORD = "Local fixture password 2026!"
VERIFIER = "teamboard-mcp-local-test-verifier-" + "x" * 32
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    .decode()
    .rstrip("=")
)


class LocalMcpFlowTests(TransactionTestCase):
    def setUp(self):
        host = urlsplit(settings.MCP_LOCAL_ISSUER).netloc
        self.browser = Client(enforce_csrf_checks=True, headers={"Host": host})
        self.host = host
        self.actor = get_user_model().objects.create_user(
            email="actor@example.invalid",
            password=PASSWORD,
            is_email_verified=True,
        )
        self.other = get_user_model().objects.create_user(
            email="another@example.invalid",
            password=PASSWORD,
            is_email_verified=True,
        )
        self.app = get_application_model().objects.create(
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris=CALLBACK,
            name="Local fixture",
            client_secret="",
        )
        self.authorize = {
            "client_id": self.app.client_id,
            "redirect_uri": CALLBACK,
            "response_type": "code",
            "scope": "teamboard.read",
            "state": "local-fixture-state",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
            "resource": settings.MCP_LOCAL_RESOURCE,
        }

    def login(self, actor):
        outcome = self.browser.post(
            "/api/v1/accounts/login/",
            {
                "email": actor.email,
                "password": PASSWORD,
            },
            content_type="application/json",
        )
        self.assertEqual(outcome.status_code, 200, outcome.content)
        return outcome.json()["access"]

    def begin(self):
        response = self.browser.get("/oauth/authorize/", self.authorize)
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(urlsplit(response["Location"]).path, "/ai/authorize")
        self.assertTrue(response.cookies[BROWSER_COOKIE]["httponly"])
        self.assertEqual(response.cookies[BROWSER_COOKIE]["samesite"], "Lax")
        return parse_qs(urlsplit(response["Location"]).fragment)["interaction"][0]

    def consent_headers(self, interaction, access):
        return {
            "Authorization": f"Bearer {access}",
            "Origin": settings.MCP_LOCAL_FRONTEND_ORIGIN,
            "X-TeamBoard-AI-Interaction": interaction,
        }

    def decision(self, headers, allow=True):
        return self.browser.post(
            "/api/v1/ai/consent/",
            {"allow": allow},
            content_type="application/json",
            headers=headers,
        )

    def oauth_post(self, data, path="/oauth/token/"):
        return self.browser.post(
            path, urlencode(data), content_type="application/x-www-form-urlencoded"
        )

    def approve_code(self, access):
        interaction = self.begin()
        headers = self.consent_headers(interaction, access)
        self.assertEqual(
            self.browser.get("/api/v1/ai/consent/", headers=headers).status_code, 200
        )
        approval = self.decision(headers)
        self.assertEqual(approval.status_code, 200, approval.content)
        self.assertEqual(self.decision(headers).status_code, 404)
        return parse_qs(urlsplit(approval.json()["redirect_url"]).query)

    def exchange_args(self, query):
        return {
            "client_id": self.app.client_id,
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": CALLBACK,
            "code_verifier": VERIFIER,
            "resource": settings.MCP_LOCAL_RESOURCE,
        }

    def test_consent_requires_original_browser_frontend_and_reviewing_account(self):
        interaction = self.begin()
        token = self.login(self.actor)
        headers = self.consent_headers(interaction, token)
        foreign = Client(headers={"Host": self.host})
        self.assertEqual(
            foreign.get("/api/v1/ai/consent/", headers=headers).status_code, 404
        )
        self.assertEqual(self.decision(headers).status_code, 403)
        self.assertEqual(
            self.browser.get(
                "/api/v1/ai/consent/",
                headers={**headers, "Origin": "http://untrusted.invalid"},
            ).status_code,
            403,
        )
        review = self.browser.get("/api/v1/ai/consent/", headers=headers)
        self.assertEqual(review.status_code, 200)
        self.assertEqual(
            review.json(),
            {
                "client_name": "Local fixture",
                "scopes": ["teamboard.read"],
                "account_email": self.actor.email,
                "callback": CALLBACK,
            },
        )
        other = self.consent_headers(interaction, self.login(self.other))
        self.assertEqual(self.decision(other).status_code, 404)
        denial = self.decision(headers, allow=False)
        self.assertEqual(denial.status_code, 200)
        self.assertEqual(
            parse_qs(urlsplit(denial.json()["redirect_url"]).query)["error"],
            ["access_denied"],
        )
        self.assertEqual(self.decision(headers).status_code, 404)

    def test_oauth_discovery_rejects_invalid_requests_and_has_no_registration(self):
        metadata = self.browser.get("/.well-known/oauth-authorization-server").json()
        self.assertEqual(metadata["issuer"], settings.MCP_LOCAL_ISSUER)
        self.assertEqual(metadata["code_challenge_methods_supported"], ["S256"])
        self.assertNotIn("registration_endpoint", metadata)
        for changes in (
            {"redirect_uri": "http://127.0.0.1:6275/callback"},
            {"redirect_uri": "https://untrusted.invalid/callback"},
            {"code_challenge_method": "plain"},
            {"resource": settings.MCP_LOCAL_ISSUER + "/different"},
            {"scope": "teamboard.write"},
        ):
            with self.subTest(changes=changes):
                response = self.browser.get(
                    "/oauth/authorize/", {**self.authorize, **changes}
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.has_header("Location"))

    def test_real_login_oauth_mcp_tenant_isolation_refresh_and_revocation(self):
        visible = Workspace.objects.create(name="Visible fixture")
        private = Workspace.objects.create(name="Private fixture")
        WorkspaceMembership.objects.create(
            workspace=visible, user=self.actor, role="member"
        )
        WorkspaceMembership.objects.create(
            workspace=private, user=self.other, role="owner"
        )
        web_access = self.login(self.actor)
        query = self.approve_code(web_access)
        self.assertEqual(query["state"], ["local-fixture-state"])
        self.assertEqual(query["iss"], [settings.MCP_LOCAL_ISSUER])
        exchange = self.exchange_args(query)
        self.assertEqual(
            self.oauth_post({**exchange, "code_verifier": "x" * 50}).status_code, 400
        )
        issued = self.oauth_post(exchange)
        self.assertEqual(issued.status_code, 200, issued.json().get("error"))
        access = issued.json()
        self.assertEqual(self.oauth_post(exchange).status_code, 400)
        access_row = get_access_token_model().objects.get(user=self.actor)
        self.assertEqual(access_row.resource, [settings.MCP_LOCAL_RESOURCE])
        self.assertEqual(access_row.token, "")
        self.assertEqual(
            get_refresh_token_model().objects.get(user=self.actor).token, ""
        )

        async def assert_tools():
            base = {"Accept": "application/json, text/event-stream"}
            async with mcp_test_client() as client:

                async def post(method, arguments, token=None, version="2025-11-25"):
                    headers = {
                        **base,
                        "MCP-Protocol-Version": version,
                        "Mcp-Method": method,
                    }
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    if method == "tools/call":
                        headers["Mcp-Name"] = arguments["name"]
                    if version == "2026-07-28":
                        arguments = {
                            **arguments,
                            "_meta": {
                                "io.modelcontextprotocol/protocolVersion": version,
                                "io.modelcontextprotocol/clientInfo": {
                                    "name": "test",
                                    "version": "1",
                                },
                                "io.modelcontextprotocol/clientCapabilities": {},
                            },
                        }
                    return await client.post(
                        "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "method": method,
                            "id": 1,
                            "params": arguments,
                        },
                    )

                denied = await post("tools/list", {})
                self.assertEqual(denied.status_code, 401)
                self.assertIn("resource_metadata", denied.headers["WWW-Authenticate"])
                self.assertEqual(
                    (await post("tools/list", {}, web_access)).status_code, 401
                )
                token = access["access_token"]
                with patch(
                    "config.mcp_local_asgi.mcp_rate_limit",
                    AsyncMock(side_effect=OSError),
                ):
                    self.assertEqual(
                        (await post("tools/list", {}, token)).status_code, 503
                    )
                versions = ("2025-11-25", "2026-07-28")
                replies = await asyncio.gather(
                    *(
                        post(
                            "tools/call",
                            {
                                "name": "teamboard_list_workspaces",
                                "arguments": {"page": 1, "page_size": 1},
                            },
                            token,
                            version,
                        )
                        for version in versions
                    )
                )
                for reply in replies:
                    self.assertEqual(reply.status_code, 200, reply.text)
                    result = reply.json()["result"]["structuredContent"]
                    self.assertEqual(
                        [row["slug"] for row in result["results"]], [visible.slug]
                    )
                    self.assertEqual(result["results"][0]["role"], "member")
                    self.assertIsNone(result["next_page"])
                refused = await post(
                    "tools/call",
                    {
                        "name": "teamboard_get_workspace",
                        "arguments": {"slug": private.slug},
                    },
                    token,
                )
                self.assertTrue(refused.json()["result"]["isError"])
                self.assertIn(
                    "NOT_FOUND", refused.json()["result"]["content"][0]["text"]
                )
                identity = await post(
                    "tools/call", {"name": "teamboard_whoami", "arguments": {}}, token
                )
                self.assertEqual(
                    identity.json()["result"]["structuredContent"]["email"],
                    self.actor.email,
                )
                invalid = await post(
                    "tools/call",
                    {
                        "name": "teamboard_list_workspaces",
                        "arguments": {"page_size": 200},
                    },
                    token,
                )
                self.assertTrue(invalid.json()["result"]["isError"])

        asyncio.run(assert_tools())
        renewed = self.oauth_post(
            {
                "client_id": self.app.client_id,
                "grant_type": "refresh_token",
                "refresh_token": access["refresh_token"],
            }
        )
        self.assertEqual(renewed.status_code, 200, renewed.json().get("error"))
        self.assertNotEqual(renewed.json()["refresh_token"], access["refresh_token"])
        self.assertEqual(
            self.oauth_post(
                {
                    "client_id": self.app.client_id,
                    "token": renewed.json()["refresh_token"],
                },
                "/oauth/revoke/",
            ).status_code,
            200,
        )
        self.assertFalse(
            get_access_token_model().objects.filter(user=self.actor).exists()
        )
        self.assertIsNone(
            asyncio.run(
                mcp_local_asgi.LocalTokenVerifier().verify_token(
                    renewed.json()["access_token"]
                )
            )
        )

    def test_existing_authenticated_chat_websocket_reaches_django(self):
        workspace = Workspace.objects.create(name="Chat fixture")
        WorkspaceMembership.objects.create(workspace=workspace, user=self.actor)
        user_low, user_high = sorted((self.actor.pk, self.other.pk))
        conversation = Conversation.objects.create(
            workspace=workspace,
            type=Conversation.Type.DIRECT,
            direct_user_low_id=user_low,
            direct_user_high_id=user_high,
        )
        access = self.login(self.actor)
        path = f"/ws/chats/{workspace.slug}/{conversation.pk}/"
        origin = settings.MCP_LOCAL_FRONTEND_ORIGIN.encode()

        async def connect():
            socket = WebsocketCommunicator(
                mcp_local_asgi.application,
                path,
                headers=[(b"origin", origin)],
                subprotocols=["jwt", access],
            )
            socket.scope["client"] = ("127.0.0.1", 51234)
            try:
                self.assertEqual(await socket.connect(), (True, "jwt"))
            finally:
                await socket.disconnect()

        asyncio.run(connect())

    def test_only_one_concurrent_exchange_consumes_an_oauth_code(self):
        exchange = self.exchange_args(self.approve_code(self.login(self.actor)))
        barrier = Barrier(2)

        def attempt():
            try:
                browser = Client(headers={"Host": self.host})
                barrier.wait(timeout=10)
                return browser.post(
                    "/oauth/token/",
                    urlencode(exchange),
                    content_type="application/x-www-form-urlencoded",
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempts = [executor.submit(attempt) for _ in range(2)]
            self.assertEqual(
                sorted(attempt.result(timeout=15) for attempt in attempts), [200, 400]
            )
        self.assertEqual(
            get_access_token_model().objects.filter(user=self.actor).count(), 1
        )
