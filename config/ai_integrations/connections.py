import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.db import transaction
from django.db.models import Min, Q
from django.utils import timezone
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
)
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuthorizationInteraction, TaskDeletionApproval
from .security import MCP_SCOPES, REFRESH_IDLE_SECONDS, lock_account

logger = logging.getLogger(__name__)
PAGE_SIZE = 20


class ConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class ConnectionListView(ConnectionView):
    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError as error:
            raise ValidationError({"page": "Use a page number from 1 to 100."}) from error
        if not 1 <= page <= 100:
            raise ValidationError({"page": "Use a page number from 1 to 100."})
        now = timezone.now()
        rows = (
            get_access_token_model().objects.filter(
                user=request.user, resource=[settings.MCP_LOCAL_RESOURCE], application__client_type__in=["public", "confidential"],
            )
            .filter(
                Q(expires__gt=now)
                | Q(refresh_token__isnull=False, refresh_token__revoked__isnull=True,
                    expires__gt=now - timedelta(seconds=REFRESH_IDLE_SECONDS))
            )
            .values("application_id", "application__name")
            .annotate(current_grant_at=Min("created"), granted=ArrayAgg("scope", distinct=True))
            .order_by("application__name", "application_id")
        )
        start = (page - 1) * PAGE_SIZE
        rows = list(rows[start : start + PAGE_SIZE + 1])
        return Response({
            "results": [
                {
                    "id": row["application_id"],
                    "name": row["application__name"],
                    "scopes": sorted({scope for grant in row["granted"] for scope in grant.split() if scope in MCP_SCOPES}),
                    "current_grant_at": row["current_grant_at"],
                }
                for row in rows[:PAGE_SIZE]
            ],
            "next_page": page + 1 if len(rows) > PAGE_SIZE and page < 100 else None,
        })


class RevokeConnectionsView(ConnectionView):
    @transaction.atomic
    def post(self, request, connection_id=None):
        user = request.user
        if not lock_account(user.pk):
            raise PermissionDenied()
        resource = [settings.MCP_LOCAL_RESOURCE]
        grants = get_grant_model().objects.filter(user=user, resource=resource)
        connections = AuthorizationInteraction.objects.filter(user=user)
        approvals = TaskDeletionApproval.objects.filter(user=user, decided_at__isnull=True)
        access = get_access_token_model().objects.filter(user=user, resource=resource)
        refresh = get_refresh_token_model().objects.filter(user=user, resource=resource)
        if connection_id is not None:
            grants = grants.filter(application_id=connection_id)
            access = access.filter(application_id=connection_id)
            refresh = refresh.filter(application_id=connection_id)
            client_ids = get_application_model().objects.filter(
                pk=connection_id,
            ).values("client_id")
            connections = connections.filter(client_id__in=client_ids)
            approvals = approvals.filter(client_id__in=client_ids)
        connections.delete()
        approvals.delete()
        grants.delete()
        refresh.filter(revoked__isnull=True).update(revoked=timezone.now())
        access.delete()
        logger.info("AI connections revoked", extra={"actor_id": user.pk, "connection_id": connection_id})
        return Response(status=204)
