from datetime import datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from oauth2_provider.models import get_access_token_model
from pydantic import BaseModel
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from tasks.access import get_task_or_404
from tasks.services import TASK_MANAGER_ROLES, _lock_project, delete_task

from .connections import ConnectionView
from .models import TaskDeletionApproval
from .security import SENSITIVE_SCOPE, allowed_client, lock_account
from .tool_schema import WorkspaceSlug


class ApprovalRequested(BaseModel):
    approval_id: UUID
    review_url: str
    expires_at: datetime


def _task(user, workspace_slug, project_id, task_id):
    return get_task_or_404(
        user=user, workspace_slug=workspace_slug, project_id=project_id,
        task_id=task_id, roles=TASK_MANAGER_ROLES,
    )


def register_approval_tools(server, annotations, write):
    @server.tool(annotations=annotations)
    async def teamboard_request_task_deletion(
        workspace_slug: WorkspaceSlug, project_id: UUID, task_id: UUID, idempotency_key: UUID,
    ) -> ApprovalRequested:
        """Request a task deletion. Direct the user to TeamBoard to review and decide."""
        token = get_access_token()
        if token is None or SENSITIVE_SCOPE not in token.scopes:
            raise ToolError("FORBIDDEN: This request needs the sensitive-action scope.")

        def request(user, task):
            now = timezone.now()
            stale = list(TaskDeletionApproval.objects.filter(user=user, expires_at__lte=now)
                         .order_by("expires_at").values_list("pk", flat=True)[:25])
            if stale:
                TaskDeletionApproval.objects.filter(user=user, pk__in=stale).delete()
            approval = TaskDeletionApproval.objects.create(
                user=user, client_id=token.client_id, workspace_slug=workspace_slug,
                project_id=project_id, task_id=task.pk, task_title=task.title, task_version=task.updated_at,
                expires_at=now + timedelta(minutes=10),
            )
            return {
                "approval_id": approval.pk, "expires_at": approval.expires_at,
                "review_url": f"{settings.MCP_LOCAL_FRONTEND_ORIGIN}/ai/approve-task-deletion#approval={approval.pk}",
            }

        result = await write("request_task_deletion", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, "task": task_id},
            lambda user: _task(user, workspace_slug, project_id, task_id), request)
        return ApprovalRequested(**result)


def _active_sensitive_connection(approval):
    tokens = get_access_token_model().objects.select_related("application").filter(
        user=approval.user_id, application__client_id=approval.client_id,
        resource=[settings.MCP_LOCAL_RESOURCE], expires__gt=timezone.now(),
    ).order_by("-expires")[:20]
    return any(SENSITIVE_SCOPE in token.scope.split() and allowed_client(token.application) for token in tokens)


def _check_pending(approval, user):
    if not _active_sensitive_connection(approval):
        raise PermissionDenied()
    task = _task(user, approval.workspace_slug, approval.project_id, approval.task_id)
    if task.updated_at != approval.task_version:
        raise ValidationError({"task": "The task changed. Request a new approval."})
    return task


def _review(approval):
    status = "pending"
    if approval.decided_at is not None:
        status = "approved" if approval.approved else "denied"
    return {
        "status": status, "task_id": approval.task_id, "task_title": approval.task_title,
        "expires_at": approval.expires_at,
    }


class TaskDeletionApprovalView(ConnectionView):
    def get(self, request, approval_id):
        approval = get_object_or_404(TaskDeletionApproval, pk=approval_id, user=request.user, expires_at__gt=timezone.now())
        if approval.decided_at is None:
            _check_pending(approval, request.user)
        return Response(_review(approval))

    @transaction.atomic
    def post(self, request, approval_id):
        if request.headers.get("Origin") != settings.MCP_LOCAL_FRONTEND_ORIGIN or not lock_account(request.user.pk):
            raise PermissionDenied()
        if not isinstance(request.data, dict) or set(request.data) != {"approve"} or not isinstance(request.data["approve"], bool):
            raise ValidationError({"approve": "Confirm or deny this deletion request."})
        approval = get_object_or_404(TaskDeletionApproval.objects.select_for_update(),
            pk=approval_id, user=request.user, expires_at__gt=timezone.now())
        if approval.decided_at is not None:
            return Response(_review(approval))
        if request.data["approve"]:
            _lock_project(project_id=approval.project_id)
            task = _check_pending(approval, request.user)
            delete_task(task=task, actor=request.user)
        approval.decided_at = timezone.now()
        approval.approved = request.data["approve"]
        approval.save(update_fields=["decided_at", "approved"])
        return Response(_review(approval))
