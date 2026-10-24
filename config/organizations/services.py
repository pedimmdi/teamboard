import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import OrganizationInvitation, OrganizationMembership


INVITATION_EXPIRY_DAYS = 7


def hash_invitation_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_organization_invitation_email(
    *,
    email,
    organization_name,
    invitation_url,
):
    message = (
        f"You have been invited to join {organization_name} "
        "on TeamBoard.\n\n"
        "To accept the invitation, open this link:\n"
        f"{invitation_url}\n\n"
        f"This invitation expires in {INVITATION_EXPIRY_DAYS} days. "
        "If you were not expecting this invitation, you can ignore "
        "this email."
    )

    send_mail(
        subject=f"Invitation to join {organization_name} on TeamBoard",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


@transaction.atomic
def create_organization_invitation(
    *,
    organization,
    invited_by,
    email,
):
    email = email.strip().lower()
    now = timezone.now()

    # Expired pending invitations must not block a new invitation.
    OrganizationInvitation.objects.filter(
        organization=organization,
        email=email,
        status=OrganizationInvitation.Status.PENDING,
        expires_at__lte=now,
    ).update(status=OrganizationInvitation.Status.EXPIRED)

    # An existing member must not be invited again.
    if organization.memberships.filter(
        user__email__iexact=email,
    ).exists():
        raise ValidationError({
            "email": "This user is already a member of the organization."
        })

    # Only one active invitation per organization and email.
    if OrganizationInvitation.objects.filter(
        organization=organization,
        email=email,
        status=OrganizationInvitation.Status.PENDING,
        expires_at__gt=now,
    ).exists():
        raise ValidationError({
            "email": "An active invitation already exists for this email."
        })

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)

    invitation = OrganizationInvitation.objects.create(
        organization=organization,
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
        lambda: send_organization_invitation_email(
            email=email,
            organization_name=organization.name,
            invitation_url=invitation_url,
        ),
        robust=True,
    )

    return invitation


def accept_organization_invitation(*, token, user):
    token_hash = hash_invitation_token(token)
    expired = False

    with transaction.atomic():
        invitation = (
            OrganizationInvitation.objects
            .select_for_update()
            .select_related("organization")
            .filter(token_hash=token_hash)
            .first()
        )

        if invitation is None:
            raise ValidationError({
                "token": "This invitation is invalid."
            })

        if invitation.status != OrganizationInvitation.Status.PENDING:
            raise ValidationError({
                "token": "This invitation is no longer available."
            })

        now = timezone.now()

        if invitation.expires_at <= now:
            invitation.status = OrganizationInvitation.Status.EXPIRED
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

            if OrganizationMembership.objects.filter(
                organization=invitation.organization,
                user=user,
            ).exists():
                raise ValidationError({
                    "detail": "You are already a member of this organization."
                })

            OrganizationMembership.objects.create(
                organization=invitation.organization,
                user=user,
                role=OrganizationMembership.Role.MEMBER,
            )

            invitation.status = OrganizationInvitation.Status.ACCEPTED
            invitation.accepted_at = now
            invitation.save(update_fields=["status", "accepted_at"])

    if expired:
        raise ValidationError({
            "token": "This invitation has expired."
        })

    return invitation
