import re
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
)
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import RevokeTokenView, TokenView
from oauth2_provider.views.mixins import OAuthLibMixin
from oauthlib.common import add_params_to_uri
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuthorizationInteraction
from .security import (
    READ_SCOPE,
    allowed_callback,
    allowed_client,
    allowed_scopes,
    digest,
    lock_account,
    within_rate_limit,
)

BROWSER_COOKIE = "teamboard_local_mcp"
BROWSER_NONCE = re.compile(r"^[0-9a-f]{64}$")
INTERACTION_TTL = timedelta(minutes=10)
OAUTH_PARAMS = {
    "client_id",
    "response_type",
    "redirect_uri",
    "scope",
    "state",
    "code_challenge",
    "code_challenge_method",
    "resource",
}


def oauth_error(error, status=400):
    return JsonResponse(
        {"error": error}, status=status, headers={"Cache-Control": "no-store"}
    )


class LocalOAuthValidator(OAuth2Validator):
    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        # This loopback runner enrolls exact callbacks, including their ports.
        return (
            allowed_client(request.client)
            and allowed_callback(redirect_uri)
            and redirect_uri in request.client.redirect_uris.split()
            and super().validate_redirect_uri(
                client_id, redirect_uri, request, *args, **kwargs
            )
        )

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        return (
            super().validate_code(client_id, code, client, request, *args, **kwargs)
            and allowed_client(client)
            and request.user.is_active
            and request.user.is_email_verified
        )

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        if not super().validate_refresh_token(
            refresh_token, client, request, *args, **kwargs
        ):
            return False
        return allowed_client(client) and request.user.is_active and request.user.is_email_verified


class LocalOAuthEndpoint:
    def dispatch(self, request, *args, **kwargs):
        try:
            allowed = within_rate_limit("oauth", 120)
        except Exception:
            return oauth_error("temporarily_unavailable", 503)
        if not allowed:
            response = oauth_error("temporarily_unavailable", 429)
            response["Retry-After"] = "60"
            return response
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


class LocalAuthorizeView(LocalOAuthEndpoint, OAuthLibMixin, View):
    def get(self, request):
        params = request.GET
        if (
            len(request.META.get("QUERY_STRING", "")) > 4096
            or any(
                key not in OAUTH_PARAMS or len(values) != 1
                for key, values in params.lists()
            )
            or params.get("response_type") != "code"
            or params.get("resource") != settings.MCP_LOCAL_RESOURCE
            or params.get("code_challenge_method") != "S256"
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.get("code_challenge", ""))
            or not 1 <= len(params.get("state", "")) <= 512
            or not allowed_callback(params.get("redirect_uri", ""))
        ):
            return oauth_error("invalid_request")
        try:
            scopes, credentials = self.validate_authorization_request(request)
        except OAuthToolkitError:
            return oauth_error("invalid_request")
        if not allowed_scopes(scopes):
            return oauth_error("invalid_scope")

        nonce = request.COOKIES.get(BROWSER_COOKIE, "")
        if not BROWSER_NONCE.fullmatch(nonce):
            nonce = secrets.token_hex(32)
        now = timezone.now()
        expired = list(
            AuthorizationInteraction.objects.filter(expires_at__lte=now)
            .order_by("expires_at")
            .values_list("pk", flat=True)[:50]
        )
        if expired:
            AuthorizationInteraction.objects.filter(
                pk__in=expired, expires_at__lte=now
            ).delete()
        interaction = AuthorizationInteraction.objects.create(
            browser_digest=digest(nonce),
            client_id=credentials["client_id"],
            credentials={
                **{
                    key: credentials[key]
                    for key in (
                        "client_id",
                        "redirect_uri",
                        "response_type",
                        "state",
                        "code_challenge",
                        "code_challenge_method",
                    )
                },
                "resource": [settings.MCP_LOCAL_RESOURCE],
                "teamboard_scopes": list(scopes),
            },
            expires_at=now + INTERACTION_TTL,
        )
        response = HttpResponseRedirect(
            f"{settings.MCP_LOCAL_FRONTEND_ORIGIN}/ai/authorize#interaction={interaction.pk}"
        )
        response.set_cookie(
            BROWSER_COOKIE,
            nonce,
            max_age=int(INTERACTION_TTL.total_seconds()),
            httponly=True,
            samesite="Lax",
            secure=not settings.MCP_LOOPBACK_ONLY,
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class LocalTokenView(LocalOAuthEndpoint, TokenView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if (
            request.content_type != "application/x-www-form-urlencoded"
            or len(request.body) > 8192
            or request.headers.get("Authorization")
            or any(len(values) != 1 for _, values in request.POST.lists())
        ):
            return oauth_error("invalid_request")
        grant = request.POST.get("grant_type")
        resource = request.POST.get("resource")
        if grant not in {"authorization_code", "refresh_token"}:
            return oauth_error("unsupported_grant_type")
        if resource is not None and resource != settings.MCP_LOCAL_RESOURCE:
            return oauth_error("invalid_target")
        if grant == "authorization_code" and resource != settings.MCP_LOCAL_RESOURCE:
            return oauth_error("invalid_target")
        if grant == "authorization_code":
            tokens = get_grant_model().objects.filter(
                code=request.POST.get("code"),
                redirect_uri=request.POST.get("redirect_uri"),
            )
        else:
            refresh = request.POST.get("refresh_token", "")
            if not 1 <= len(refresh) <= 512:
                return oauth_error("invalid_grant")
            tokens = get_refresh_token_model().objects.filter(token_checksum=digest(refresh))
            scope = request.POST.get("scope")
            if scope is not None and not allowed_scopes(scope.split()):
                return oauth_error("invalid_scope")
        tokens = tokens.filter(application__client_id=request.POST.get("client_id"))
        account = tokens.values_list("user_id", flat=True).first()
        # This is also the lock obtained when account settings revoke a connection.
        if account is None or not lock_account(account):
            return oauth_error("invalid_grant")
        if not tokens.filter(user_id=account).exists():
            return oauth_error("invalid_grant")
        return super().post(request, *args, **kwargs)


@method_decorator(csrf_exempt, name="dispatch")
class LocalRevokeView(LocalOAuthEndpoint, RevokeTokenView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if (
            request.content_type != "application/x-www-form-urlencoded"
            or len(request.body) > 8192
        ):
            return oauth_error("invalid_request")
        value = request.POST.get("token", "")
        if 1 <= len(value) <= 512:
            for model in (get_access_token_model(), get_refresh_token_model()):
                account = model.objects.filter(
                    token_checksum=digest(value), application__client_id=request.POST.get("client_id"),
                    resource=[settings.MCP_LOCAL_RESOURCE],
                ).values_list("user_id", flat=True).first()
                if account is not None:
                    lock_account(account)
                    break
        return super().post(request, *args, **kwargs)


class ConsentView(OAuthLibMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def find_interaction(self, request):
        if (
            request.headers.get("Origin") != settings.MCP_LOCAL_FRONTEND_ORIGIN
            or not request.user.is_email_verified
        ):
            raise PermissionDenied()
        nonce = request.COOKIES.get(BROWSER_COOKIE, "")
        if not BROWSER_NONCE.fullmatch(nonce):
            raise NotFound("This authorization request has expired.")
        try:
            interaction_id = uuid.UUID(
                request.headers.get("X-TeamBoard-AI-Interaction", "")
            )
        except ValueError as error:
            raise NotFound("This authorization request has expired.") from error
        interaction = (
            AuthorizationInteraction.objects.select_for_update()
            .filter(
                pk=interaction_id,
                browser_digest=digest(nonce),
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not interaction or interaction.user_id not in {None, request.user.pk}:
            raise NotFound("This authorization request has expired.")
        return interaction

    @transaction.atomic
    def get(self, request):
        interaction = self.find_interaction(request)
        application = (
            get_application_model()
            .objects.filter(client_id=interaction.client_id)
            .first()
        )
        if not allowed_client(application):
            raise NotFound("This authorization request has expired.")
        if interaction.user_id is None:
            interaction.user = request.user
            interaction.save(update_fields=["user"])
        return Response(
            {
                "client_name": application.name,
                "account_email": request.user.email,
                "scopes": interaction.credentials.get("teamboard_scopes", [READ_SCOPE]),
                "callback": interaction.credentials["redirect_uri"],
            }
        )

    @transaction.atomic
    def post(self, request):
        if (
            not isinstance(request.data, dict)
            or set(request.data) != {"allow"}
            or not isinstance(request.data["allow"], bool)
        ):
            raise ValidationError({"allow": "Choose whether to allow this connection."})
        if not lock_account(request.user.pk):
            raise PermissionDenied()
        interaction = self.find_interaction(request)
        if interaction.user_id != request.user.pk:
            raise PermissionDenied()
        credentials = dict(interaction.credentials)
        scopes = credentials.pop("teamboard_scopes", [READ_SCOPE])
        if request.data["allow"]:
            try:
                location, _, _, status = self.create_authorization_response(
                    request._request, " ".join(scopes), credentials, True
                )
            except OAuthToolkitError as error:
                raise NotFound("This authorization request has expired.") from error
            if status != 302 or not location or not allowed_callback(location, initial=False):
                raise ValidationError("Unable to authorize this connection.")
        else:
            location = add_params_to_uri(
                credentials["redirect_uri"],
                {
                    "error": "access_denied",
                    "state": credentials["state"],
                    "iss": settings.MCP_LOCAL_ISSUER,
                },
            )
        interaction.delete()
        return Response({"redirect_url": location})
