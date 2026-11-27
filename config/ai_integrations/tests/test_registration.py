import base64
import hashlib
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.conf import settings

if settings.SETTINGS_MODULE != "config.mcp_local_settings":
    pytest.skip("Run with --ds=config.mcp_local_settings.", allow_module_level=True)

from config.mcp_oauth_settings import oauth_settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from oauth2_provider.models import get_application_model

ISSUER = "https://api.teamboard-tests.com"
FRONTEND = "https://app.teamboard-tests.com"
CALLBACK = "https://client.teamboard-tests.com/return"
PASSWORD = "Test OAuth client registration only"


@pytest.mark.django_db(transaction=True)
@override_settings(
    MCP_LOOPBACK_ONLY=False,
    MCP_LOCAL_ISSUER=ISSUER,
    MCP_LOCAL_FRONTEND_ORIGIN=FRONTEND,
    MCP_LOCAL_RESOURCE=ISSUER + "/mcp",
    MCP_CLIENT_CALLBACKS={CALLBACK: "Approved provider"},
    ALLOWED_HOSTS=["api.teamboard-tests.com"],
    OAUTH2_PROVIDER={**oauth_settings(ISSUER, ["https"], confidential=True), "DCR_ENABLED": True},
)
def test_https_oauth_discovery_registration_and_confidential_client_exchange():
    client = Client(headers={"Host": "api.teamboard-tests.com"})

    def json_post(path, value, **options):
        return client.post(path, value, content_type="application/json", secure=True, **options)

    metadata = client.get("/.well-known/oauth-authorization-server", secure=True).json()
    assert metadata["issuer"] == ISSUER
    assert metadata["registration_endpoint"] == ISSUER + "/oauth/register/"
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    resource = client.get("/.well-known/oauth-protected-resource/mcp", secure=True).json()
    assert resource["resource"] == ISSUER + "/mcp"
    assert "teamboard.write" in resource["scopes_supported"]
    callback_data = {"client_name": "Untrusted name", "token_endpoint_auth_method": "client_secret_post"}
    for uri in ["https://unexpected.example.com/callback", CALLBACK + "?redirect=attacker", "http://127.0.0.1:1234"]:
        assert json_post("/oauth/register/", {**callback_data, "redirect_uris": [uri]}).status_code == 400
    registration = json_post("/oauth/register/", {**callback_data, "redirect_uris": [CALLBACK]})
    assert registration.status_code == 201, registration.content
    assert registration.headers["Cache-Control"] == "no-store"
    approved = registration.json()
    assert approved["client_name"] == "Approved provider"
    assert get_application_model().objects.get(client_id=approved["client_id"]).client_secret != approved["client_secret"]

    user = get_user_model().objects.create_user(email="mcp-hosted-fixture@example.invalid", password=PASSWORD, is_email_verified=True)
    verifier = "c" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    start = client.get("/oauth/authorize/", {
        "client_id": approved["client_id"], "redirect_uri": CALLBACK, "response_type": "code",
        "scope": "teamboard.read teamboard.write", "state": "bound-state", "resource": ISSUER + "/mcp",
        "code_challenge": challenge, "code_challenge_method": "S256",
    }, secure=True)
    assert start.status_code == 302, start.content
    assert start.cookies["teamboard_local_mcp"]["secure"]
    interaction = parse_qs(urlsplit(start.headers["Location"]).fragment)["interaction"][0]
    jwt = json_post("/api/v1/accounts/login/", {"email": user.email, "password": PASSWORD}).json()["access"]
    headers = {"Authorization": f"Bearer {jwt}", "Origin": FRONTEND, "X-TeamBoard-AI-Interaction": interaction}
    assert client.get("/api/v1/ai/consent/", headers=headers, secure=True).status_code == 200
    review = json_post("/api/v1/ai/consent/", {"allow": True}, headers=headers)
    assert review.status_code == 200, review.content
    query = parse_qs(urlsplit(review.json()["redirect_url"]).query)
    assert query["state"] == ["bound-state"]
    assert query["iss"] == [ISSUER]
    exchange = {
        "grant_type": "authorization_code", "client_id": approved["client_id"], "code": query["code"][0],
        "redirect_uri": CALLBACK, "resource": ISSUER + "/mcp", "code_verifier": verifier,
    }

    def token(data):
        return client.post("/oauth/token/", urlencode(data), content_type="application/x-www-form-urlencoded", secure=True)

    assert token({**exchange, "client_secret": "wrong"}).status_code == 401
    issued = token({**exchange, "client_secret": approved["client_secret"]})
    assert issued.status_code == 200, issued.json().get("error")
    assert set(issued.json()["scope"].split()) == {"teamboard.read", "teamboard.write"}
