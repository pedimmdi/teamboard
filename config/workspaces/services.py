import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import WorkspaceInvitation, WorkspaceMembership


INVITATION_EXPIRY_DAYS = 7


def hash_invitation_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_workspace_invitation_email(
    *,
    email,
    workspace_name,
    invitation_url,
):
    message = (
        f"You have been invited to join {workspace_name} "
        "on TeamBoard.\n\n"
        "To accept the invitation, open this link:\n"
        f"{invitation_url}\n\n"
        f"This invitation expires in {INVITATION_EXPIRY_DAYS} days. "
        "If you were not expecting this invitation, you can ignore "
        "this email."
    )

    send_mail(
        subject=f"Invitation to join {workspace_name} on TeamBoard",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


@transaction.atomic
def create_workspace_invitation(
    *,
    workspace,
    invited_by,
    email,
):
    email = email.strip().lower()
    now = timezone.now()

    # Expired pending invitations must not block a new invitation.
    WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email=email,
        status=WorkspaceInvitation.Status.PENDING,
        expires_at__lte=now,
    ).update(status=WorkspaceInvitation.Status.EXPIRED)

    # An existing member must not be invited again.
    if workspace.memberships.filter(
        user__email__iexact=email,
    ).exists():
        raise ValidationError({
            "email": "This user is already a member of the workspace."
        })

    # Only one active invitation per workspace and email.
    if WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email=email,
        status=WorkspaceInvitation.Status.PENDING,
        expires_at__gt=now,
    ).exists():
        raise ValidationError({
            "email": "An active invitation already exists for this email."
        })

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)

    invitation = WorkspaceInvitation.objects.create(
        workspace=workspace,
        email=email,
        invited_by=invited_by,
        token_hash=token_hash,
        expires_at=now + timedelta(days=INVITATION_EXPIRY_DAYS),
    )

    invitation_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/accept-invitation/"
        f"?token={raw_token}"
    )

    # Email delivery happens only after the database transaction commits.
    transaction.on_commit(
        lambda: send_workspace_invitation_email(
            email=email,
            workspace_name=workspace.name,
            invitation_url=invitation_url,
        ),
        robust=True,
    )

    return invitation


def accept_workspace_invitation(*, token, user):
    token_hash = hash_invitation_token(token)
    expired = False

    with transaction.atomic():
        invitation = (
            WorkspaceInvitation.objects
            .select_for_update()
            .select_related("workspace")
            .filter(token_hash=token_hash)
            .first()
        )

        if invitation is None:
            raise ValidationError({
                "token": "This invitation is invalid."
            })

        if invitation.status != WorkspaceInvitation.Status.PENDING:
            raise ValidationError({
                "token": "This invitation is no longer available."
            })

        now = timezone.now()

        if invitation.expires_at <= now:
            invitation.status = WorkspaceInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            expired = True
        else:
            if not user.is_active:
                raise ValidationError({
                    "detail": "Your account is not active."
                })

            if not getattr(user, "is_email_verified", False):
                raise ValidationError({
                    "email": "You must verify your email before accepting an invitation."
                })

            if user.email.strip().lower() != invitation.email.strip().lower():
                raise ValidationError({
                    "email": "Your verified account email does not match the invitation."
                })

            if WorkspaceMembership.objects.filter(
                workspace=invitation.workspace,
                user=user,
            ).exists():
                raise ValidationError({
                    "detail": "You are already a member of this workspace."
                })

            WorkspaceMembership.objects.create(
                workspace=invitation.workspace,
                user=user,
                role=WorkspaceMembership.Role.MEMBER,
            )

            invitation.status = WorkspaceInvitation.Status.ACCEPTED
            invitation.accepted_at = now
            invitation.save(update_fields=["status", "accepted_at"])

    if expired:
        raise ValidationError({
            "token": "This invitation has expired."
        })

    return invitation


@transaction.atomic
def resend_workspace_invitation(
    *,
    workspace,
    invitation_id,
    invited_by,
):
    now = timezone.now()

    try:
        invitation = (
            WorkspaceInvitation.objects
            .select_for_update()
            .select_related("workspace")
            .get(
                id=invitation_id,
                workspace=workspace,
            )
        )
    except WorkspaceInvitation.DoesNotExist:
        from rest_framework.exceptions import NotFound

        raise NotFound("Invitation not found.")

    if invitation.status in (
        WorkspaceInvitation.Status.ACCEPTED,
        WorkspaceInvitation.Status.REVOKED,
    ):
        raise ValidationError({
            "status": (
                "Accepted or revoked invitations cannot be resent."
            )
        })

    # An existing member does not need another invitation.
    if workspace.memberships.filter(
        user__email__iexact=invitation.email,
    ).exists():
        raise ValidationError({
            "email": "This user is already a member of the workspace."
        })

    # Clear stale pending records for this email before reactivating
    # this invitation, so the database uniqueness constraint is respected.
    WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email=invitation.email,
        status=WorkspaceInvitation.Status.PENDING,
        expires_at__lte=now,
    ).exclude(
        pk=invitation.pk,
    ).update(
        status=WorkspaceInvitation.Status.EXPIRED,
    )

    # Do not create multiple active invitations for the same email.
    active_invitation_exists = (
        WorkspaceInvitation.objects.filter(
            workspace=workspace,
            email=invitation.email,
            status=WorkspaceInvitation.Status.PENDING,
            expires_at__gt=now,
        )
        .exclude(pk=invitation.pk)
        .exists()
    )

    if active_invitation_exists:
        raise ValidationError({
            "status": (
                "Another active invitation already exists for this email."
            )
        })

    raw_token = secrets.token_urlsafe(32)

    invitation.token_hash = hash_invitation_token(raw_token)
    invitation.status = WorkspaceInvitation.Status.PENDING
    invitation.expires_at = now + timedelta(
        days=INVITATION_EXPIRY_DAYS,
    )
    invitation.invited_by = invited_by

    invitation.save(
        update_fields=[
            "token_hash",
            "status",
            "expires_at",
            "invited_by",
        ]
    )

    invitation_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/accept-invitation/"
        f"?token={raw_token}"
    )

    transaction.on_commit(
        lambda: send_workspace_invitation_email(
            email=invitation.email,
            workspace_name=workspace.name,
            invitation_url=invitation_url,
        ),
        robust=True,
    )

    return invitation
