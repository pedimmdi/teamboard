
"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import {
  ApiError,
  getOrganizationInvitations,
  resendOrganizationInvitation,
  type OrganizationInvitation,
} from "@/lib/api";

import { useOrganization } from "../organization-context";
import InviteMemberModal from "./invite-member-modal";
import InvitationActions from "./invitation-actions";
import RevokeInvitationModal from "./revoke-invitation-modal";
import styles from "./invitations.module.css";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatStatus(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export default function InvitationsPage() {
  const { accessToken } = useAuth();
  const organization = useOrganization();

  const canManageInvitations =
    organization.role === "owner" ||
    organization.role === "admin";

  const [invitations, setInvitations] = useState<
    OrganizationInvitation[]
  >([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [revokingInvitation, setRevokingInvitation] =
    useState<OrganizationInvitation | null>(null);

  const [resendingInvitationId, setResendingInvitationId] =
    useState<string | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !canManageInvitations) return;

    const token = accessToken;
    let cancelled = false;

    async function loadInvitations() {
      setIsLoading(true);
      setError(null);

      try {
        const data = await getOrganizationInvitations(
          token,
          organization.slug,
          page,
        );

        if (cancelled) return;

        if (page > 1 && data.results.length === 0) {
          setPage(page - 1);
          return;
        }

        setInvitations(data.results);
        setCount(data.count);
        setHasNext(Boolean(data.next));
        setHasPrevious(Boolean(data.previous));
      } catch (err) {
        if (cancelled) return;

        setError(
          err instanceof ApiError
            ? err.message
            : "Unable to load invitations.",
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadInvitations();

    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    canManageInvitations,
    organization.slug,
    page,
    reloadKey,
  ]);

  async function handleResend(invitation: OrganizationInvitation) {
    if (!accessToken || resendingInvitationId) return;

    setResendingInvitationId(invitation.id);
    setActionError(null);
    setActionSuccess(null);

    try {
      await resendOrganizationInvitation(
        accessToken,
        organization.slug,
        invitation.id,
      );

      setActionSuccess(`Invitation resent to ${invitation.email}.`);
      setReloadKey((value) => value + 1);
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.message
          : "Unable to resend invitation.",
      );
    } finally {
      setResendingInvitationId(null);
    }
  }

  if (!canManageInvitations) {
    return (
      <section className={styles.section}>
        <h2>Invitations</h2>
        <div className={styles.status}>
          Only organization owners and admins can manage invitations.
        </div>
      </section>
    );
  }

  return (
    <section className={styles.section}>
      <div className={styles.heading}>
        <div>
          <h2>Invitations</h2>
          <p>Manage invitations to your organization.</p>
        </div>

        <div className={styles.headingActions}>
          <span className={styles.count}>
            {count} invitations
          </span>

          <button
            type="button"
            className={styles.inviteButton}
            onClick={() => {
              setActionError(null);
              setActionSuccess(null);
              setIsInviteModalOpen(true);
            }}
          >
            + Invite member
          </button>
        </div>
      </div>

      {actionError && (
        <div className={styles.actionError} role="alert">
          {actionError}
        </div>
      )}

      {actionSuccess && (
        <div className={styles.actionSuccess} role="status">
          {actionSuccess}
        </div>
      )}

      {isLoading ? (
        <div className={styles.status}>
          Loading invitations...
        </div>
      ) : error ? (
        <div className={styles.status} role="alert">
          <p>{error}</p>
          <button
            type="button"
            onClick={() =>
              setReloadKey((value) => value + 1)
            }
          >
            Try again
          </button>
        </div>
      ) : invitations.length === 0 ? (
        <div className={styles.status}>
          No invitations found.
        </div>
      ) : (
        <div className={styles.card}>
          <div className={styles.desktopTable}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Sent</th>
                  <th>Expires</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>

              <tbody>
                {invitations.map((invitation) => (
                  <tr key={invitation.id}>
                    <td className={styles.email}>
                      {invitation.email}
                    </td>
                    <td>
                      <span
                        className={`${styles.badge} ${
                          styles[invitation.status]
                        }`}
                      >
                        {formatStatus(invitation.status)}
                      </span>
                    </td>
                    <td>{formatDate(invitation.created_at)}</td>
                    <td>{formatDate(invitation.expires_at)}</td>
                    <td className={styles.actionCell}>
                      {resendingInvitationId ? (
                        <span className={styles.actionLoading}>
                          {resendingInvitationId === invitation.id ? "Sending..." : ""}
                        </span>
                      ) : (
                        <InvitationActions
                          invitation={invitation}
                          onResend={() => void handleResend(invitation)}
                          onRevoke={() => {
                            setActionError(null);
                            setActionSuccess(null);
                            setRevokingInvitation(invitation);
                          }}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.mobileList}>
            {invitations.map((invitation) => (
              <div
                key={invitation.id}
                className={styles.mobileCard}
              >
                <div className={styles.mobileTop}>
                  <strong className={styles.email}>
                    {invitation.email}
                  </strong>

                  <span
                    className={`${styles.badge} ${
                      styles[invitation.status]
                    }`}
                  >
                    {formatStatus(invitation.status)}
                  </span>
                </div>

                <div className={styles.mobileDates}>
                  <span>
                    Sent: {formatDate(invitation.created_at)}
                  </span>
                  <span>
                    Expires: {formatDate(invitation.expires_at)}
                  </span>
                </div>
                <div className={styles.mobileActions}>
                  {resendingInvitationId ? (
                    <span className={styles.actionLoading}>
                      {resendingInvitationId === invitation.id ? "Sending..." : ""}
                    </span>
                  ) : (
                    <InvitationActions
                      invitation={invitation}
                      onResend={() => void handleResend(invitation)}
                      onRevoke={() => {
                        setActionError(null);
                        setActionSuccess(null);
                        setRevokingInvitation(invitation);
                      }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className={styles.footer}>
            <span>{count} invitations total</span>

            <div className={styles.pagination}>
              <button
                type="button"
                disabled={!hasPrevious || isLoading}
                onClick={() =>
                  setPage((value) => Math.max(1, value - 1))
                }
              >
                Previous
              </button>

              <button
                type="button"
                disabled={!hasNext || isLoading}
                onClick={() =>
                  setPage((value) => value + 1)
                }
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {isInviteModalOpen && accessToken && (
        <InviteMemberModal
          accessToken={accessToken}
          slug={organization.slug}
          onClose={() => setIsInviteModalOpen(false)}
          onInvited={() => {
            setIsInviteModalOpen(false);
            setActionError(null);
            setActionSuccess("Invitation sent successfully.");
            setPage(1);
            setReloadKey((value) => value + 1);
          }}
        />
      )}

      {revokingInvitation && accessToken && (
        <RevokeInvitationModal
          accessToken={accessToken}
          slug={organization.slug}
          invitation={revokingInvitation}
          onClose={() => setRevokingInvitation(null)}
          onRevoked={() => {
            setRevokingInvitation(null);
            setActionError(null);
            setActionSuccess("Invitation revoked successfully.");
            setReloadKey((value) => value + 1);
          }}
        />
      )}
    </section>
  );
}
