
"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useTransientMessage } from "@/hooks/use-transient-message";

import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import {
  ApiError,
  getWorkspaceInvitations,
  resendWorkspaceInvitation,
  type WorkspaceInvitation,
} from "@/lib/api";

import { useWorkspace } from "../workspace-context";
import InviteMemberModal from "./invite-member-modal";
import InvitationActions from "./invitation-actions";
import RevokeInvitationModal from "./revoke-invitation-modal";
import styles from "./invitations.module.css";

function formatStatus(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export default function InvitationsPage() {
  const { ui, formatDate, formatNumber } = useWorkspaceLocale();
  const { accessToken } = useAuth();
  const workspace = useWorkspace();

  const canManageInvitations =
    workspace.role === "owner" ||
    workspace.role === "admin";

  const [invitations, setInvitations] = useState<
    WorkspaceInvitation[]
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
    useState<WorkspaceInvitation | null>(null);

  const [resendingInvitationId, setResendingInvitationId] =
    useState<string | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useTransientMessage<string | null>(null);

  useEffect(() => {
    if (!accessToken || !canManageInvitations) return;

    const token = accessToken;
    let cancelled = false;

    async function loadInvitations() {
      setIsLoading(true);
      setError(null);

      try {
        const data = await getWorkspaceInvitations(
          token,
          workspace.slug,
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
    workspace.slug,
    page,
    reloadKey,
  ]);

  async function handleResend(invitation: WorkspaceInvitation) {
    if (!accessToken || resendingInvitationId) return;

    setResendingInvitationId(invitation.id);
    setActionError(null);
    setActionSuccess(null);

    try {
      await resendWorkspaceInvitation(
        accessToken,
        workspace.slug,
        invitation.id,
      );

      setActionSuccess(ui("Invitation resent to {0}.", invitation.email));
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
        <h2>{ui("Invitations")}</h2>
        <div className={styles.status}>{ui("Only workspace owners and admins can manage invitations.")}</div>
      </section>
    );
  }

  return (
    <section className={styles.section}>
      <div className={styles.heading}>
        <div>
          <h2>{ui("Invitations")}</h2>
          <p>{ui("Manage invitations to your workspace.")}</p>
        </div>

        <div className={styles.headingActions}>
          <span className={styles.count}>
            {formatNumber(count)} {ui("invitations")}
          </span>

          <button
            type="button"
            className={styles.inviteButton}
            onClick={() => {
              setActionError(null);
              setActionSuccess(null);
              setIsInviteModalOpen(true);
            }}
          >{ui("+ Invite member")}</button>
        </div>
      </div>

      {actionError && (
        <div className={styles.actionError} role="alert">
          {ui(actionError)}
        </div>
      )}

      {actionSuccess && (
        <div className={styles.actionSuccess} role="status">
          {ui(actionSuccess)}
        </div>
      )}

      {isLoading ? (
        <div className={styles.status}>{ui("Loading invitations...")}</div>
      ) : error ? (
        <div className={styles.status} role="alert">
          <p>{ui(error)}</p>
          <button
            type="button"
            onClick={() =>
              setReloadKey((value) => value + 1)
            }
          >{ui("Try again")}</button>
        </div>
      ) : invitations.length === 0 ? (
        <div className={styles.status}>{ui("No invitations found.")}</div>
      ) : (
        <div className={styles.card}>
          <div className={styles.desktopTable}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{ui("Email")}</th>
                  <th>{ui("Status")}</th>
                  <th>{ui("Sent")}</th>
                  <th>{ui("Expires")}</th>
                  <th aria-label={ui("Actions")} />
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
                        {ui(formatStatus(invitation.status))}
                      </span>
                    </td>
                    <td>{formatDate(invitation.created_at, { month: "short", day: "2-digit", year: "numeric" })}</td>
                    <td>{formatDate(invitation.expires_at, { month: "short", day: "2-digit", year: "numeric" })}</td>
                    <td className={styles.actionCell}>
                      {resendingInvitationId ? (
                        <span className={styles.actionLoading}>
                          {resendingInvitationId === invitation.id ? ui("Sending...") : ""}
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
                    {ui(formatStatus(invitation.status))}
                  </span>
                </div>

                <div className={styles.mobileDates}>
                  <span>
                    {ui("Sent:")} {formatDate(invitation.created_at, { month: "short", day: "2-digit", year: "numeric" })}
                  </span>
                  <span>
                    {ui("Expires:")} {formatDate(invitation.expires_at, { month: "short", day: "2-digit", year: "numeric" })}
                  </span>
                </div>
                <div className={styles.mobileActions}>
                  {resendingInvitationId ? (
                    <span className={styles.actionLoading}>
                      {resendingInvitationId === invitation.id ? ui("Sending...") : ""}
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
            <span>{formatNumber(count)} {ui("invitations total")}</span>

            <div className={styles.pagination}>
              <button
                type="button"
                disabled={!hasPrevious || isLoading}
                onClick={() =>
                  setPage((value) => Math.max(1, value - 1))
                }
              >{ui("Previous")}</button>

              <button
                type="button"
                disabled={!hasNext || isLoading}
                onClick={() =>
                  setPage((value) => value + 1)
                }
              >{ui("Next")}</button>
            </div>
          </div>
        </div>
      )}

      {isInviteModalOpen && accessToken && (
        <InviteMemberModal
          accessToken={accessToken}
          slug={workspace.slug}
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
          slug={workspace.slug}
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
