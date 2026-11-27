import json
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from oauth2_provider.models import get_access_token_model
from rest_framework.throttling import ScopedRateThrottle

from .models import MutationReceipt
from .security import WRITE_SCOPE, digest, lock_account, within_rate_limit

REST_THROTTLE_SCOPES = {
    "create_workspace": "workspace_create",
    "create_project": "project_create",
    "create_task": "task_create",
    "create_task_comment": "comment_create",
    "start_direct_chat": "chat_direct_create",
    "send_chat_message": "chat_message_create",
    "create_task_reminder": "reminder_write",
    "update_task_reminder": "reminder_write",
    "cancel_task_reminder": "reminder_write",
}


def write_user_id():
    token = get_access_token()
    if token is None or not token.subject or WRITE_SCOPE not in token.scopes:
        raise ToolError("FORBIDDEN: A TeamBoard write connection is required.")
    return int(token.subject)


@transaction.atomic
def run_idempotent(user, tool_name, key, arguments, authorize, operation):
    token = get_access_token()
    if token is None or token.subject != str(user.pk) or WRITE_SCOPE not in token.scopes:
        raise ToolError("FORBIDDEN: A TeamBoard write connection is required.")
    try:
        allowed = within_rate_limit(f"write:{user.pk}", 30)
    except Exception:
        raise ToolError("TEMPORARILY_UNAVAILABLE: Try again later with the same key.") from None
    if not allowed:
        raise ToolError("RATE_LIMITED: Wait before retrying with the same key.")

    # Revalidate after acquiring the same lock used by account-side revocation.
    if not lock_account(user.pk):
        raise ToolError("FORBIDDEN: This TeamBoard account is unavailable.")
    now = timezone.now()
    stored = get_access_token_model().objects.filter(
        user=user, application__client_id=token.client_id, token_checksum=digest(token.token),
        expires__gt=now, resource=[settings.MCP_LOCAL_RESOURCE],
    ).values_list("scope", flat=True).first()
    if not stored or WRITE_SCOPE not in stored.split():
        raise ToolError("FORBIDDEN: This TeamBoard connection is unavailable.")

    authorization = authorize()
    material = json.dumps(arguments, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"))
    fingerprint = digest(material)
    receipts = MutationReceipt.objects.filter(user=user, client_id=token.client_id, tool=tool_name, key=key)
    expired = list(MutationReceipt.objects.filter(user=user, expires_at__lte=now).order_by("expires_at").values_list("pk", flat=True)[:25])
    if expired:
        MutationReceipt.objects.filter(pk__in=expired, expires_at__lte=now).delete()
    receipt = receipts.first()
    if receipt and receipt.expires_at > now:
        if receipt.input_digest != fingerprint:
            raise ToolError("CONFLICT: This idempotency key was already used with different input.")
        return receipt.result
    if receipt:
        receipt.delete()

    if scope := REST_THROTTLE_SCOPES.get(tool_name):
        try:
            allowed = ScopedRateThrottle().allow_request(
                SimpleNamespace(user=user), SimpleNamespace(throttle_scope=scope),
            )
        except Exception:
            raise ToolError("TEMPORARILY_UNAVAILABLE: Try again later with the same key.") from None
        if not allowed:
            raise ToolError("RATE_LIMITED: Wait before retrying with the same key.")

    result = json.loads(json.dumps(operation(authorization), cls=DjangoJSONEncoder))
    MutationReceipt.objects.create(
        user=user, client_id=token.client_id, tool=tool_name, key=key,
        input_digest=fingerprint, result=result, expires_at=now + timedelta(days=1),
    )
    return result
