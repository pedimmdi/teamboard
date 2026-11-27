import json
import secrets

from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_application_model

from .oauth import LocalOAuthEndpoint, oauth_error
from .security import READ_SCOPE, allowed_scopes


@method_decorator(csrf_exempt, name="dispatch")
class ClientRegistrationView(LocalOAuthEndpoint, View):
    def dispatch(self, request, *args, **kwargs):
        if settings.MCP_LOOPBACK_ONLY or not settings.MCP_CLIENT_CALLBACKS:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        if request.content_type != "application/json" or len(request.body) > 8192:
            return oauth_error("invalid_client_metadata")
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeError):
            return oauth_error("invalid_client_metadata")
        if not isinstance(data, dict):
            return oauth_error("invalid_client_metadata")
        redirects = data.get("redirect_uris")
        methods = {"none": "public", "client_secret_post": "confidential"}
        method = data.get("token_endpoint_auth_method", "client_secret_post")
        grants = data.get("grant_types", ["authorization_code", "refresh_token"])
        scope = data.get("scope", READ_SCOPE)
        if (
            not isinstance(method, str) or method not in methods
            or not isinstance(grants, list) or "authorization_code" not in grants
            or any(grant not in ("authorization_code", "refresh_token") for grant in grants)
            or data.get("response_types", ["code"]) != ["code"]
            or not isinstance(scope, str) or not allowed_scopes(scope.split())
        ):
            return oauth_error("invalid_client_metadata")
        if (
            not isinstance(redirects, list) or not 1 <= len(redirects) <= 4
            or not all(isinstance(uri, str) and uri in settings.MCP_CLIENT_CALLBACKS for uri in redirects)
            or len(set(redirects)) != len(redirects)
        ):
            return oauth_error("invalid_redirect_uri")
        names = {settings.MCP_CLIENT_CALLBACKS[uri] for uri in redirects}
        if len(names) != 1:
            return oauth_error("invalid_redirect_uri")
        name = names.pop().strip()
        secret = "" if method == "none" else secrets.token_urlsafe(48)
        application = get_application_model().objects.create(
            name=name, redirect_uris=" ".join(redirects), client_type=methods[method],
            authorization_grant_type="authorization-code", client_secret=secret, skip_authorization=False,
        )
        result = {
            "client_id": application.client_id, "client_name": name, "redirect_uris": redirects,
            "token_endpoint_auth_method": method, "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }
        if secret:
            result.update(client_secret=secret, client_secret_expires_at=0)
        return JsonResponse(result, status=201)
