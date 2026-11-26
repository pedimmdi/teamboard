
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from projects.access import get_workspace_project_membership_or_404
from workspaces.access import get_membership_or_404
from workspaces.models import WorkspaceMembership

from .models import Conversation


def get_chat_workspace(*, workspace_slug, actor):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Authentication required.")

    membership = get_membership_or_404(
        workspace_slug,
        actor,
    )
    return membership.workspace


def get_project_chat_access(*, workspace_slug, project_id, actor):
    get_chat_workspace(
        workspace_slug=workspace_slug,
        actor=actor,
    )

    access = get_workspace_project_membership_or_404(
        workspace_slug=workspace_slug,
        project_id=project_id,
        user=actor,
    )
    return access.project


def get_conversation_or_404(*, workspace_slug, conversation_id, actor):
    workspace = get_chat_workspace(
        workspace_slug=workspace_slug,
        actor=actor,
    )

    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "project",
            "workspace",
        ),
        pk=conversation_id,
        workspace=workspace,
    )

    if conversation.type == Conversation.Type.PROJECT:
        if conversation.project_id is None:
            raise Http404

        get_workspace_project_membership_or_404(
            workspace_slug=workspace_slug,
            project_id=conversation.project_id,
            user=actor,
        )
    elif conversation.type == Conversation.Type.DIRECT:
        if actor.pk not in (
            conversation.direct_user_low_id,
            conversation.direct_user_high_id,
        ):
            raise Http404
    else:
        raise Http404

    return conversation


def ensure_direct_recipient(*, workspace, recipient, actor):
    if recipient.pk == actor.pk:
        raise PermissionDenied(
            "You cannot start a direct conversation with yourself."
        )

    if not recipient.is_active:
        raise PermissionDenied(
            "The recipient is not available."
        )

    if not WorkspaceMembership.objects.filter(
        workspace=workspace,
        user=recipient,
    ).exists():
        raise PermissionDenied(
            "The recipient must belong to this workspace."
        )
