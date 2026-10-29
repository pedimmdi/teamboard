
"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  acceptOrganizationInvitation,
  ApiError,
  type AcceptOrganizationInvitationResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { clearInvitationReturn, saveInvitationReturn } from "@/lib/invitation-return";

import styles from "./accept-invitation.module.css";

type InvitationStatus = "ready" | "success" | "error";

function Brand() {
  return (
    <Link href="/" className={styles.brand}>
      <span className={styles.brandMark}>T</span>
      <span>TeamBoard</span>
    </Link>
  );
}

function StatusIcon({
  status,
}: {
  status: "ready" | "success" | "error";
}) {
  return (
    <div className={`${styles.iconCircle} ${styles[status]}`}>
      {status === "ready" ? (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="4" y="6" width="16" height="12" rx="2" />
          <path d="m5 8 7 5 7-5" />
        </svg>
      ) : status === "success" ? (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="m8.5 12 2.5 2.5 4.5-5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v5M12 16h.01" />
        </svg>
      )}
    </div>
  );
}

function InvitationContent() {
  const searchParams = useSearchParams();
  const invitationToken = searchParams.get("token")?.trim() ?? "";

  const {
    accessToken,
    isAuthenticated,
    isLoading,
    user,
    logout,
  } = useAuth();

  const router = useRouter();
  const [isSwitchingAccount, setIsSwitchingAccount] = useState(false);

  const [result, setResult] =
    useState<AcceptOrganizationInvitationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const status: InvitationStatus = result
    ? "success"
    : !invitationToken || error
      ? "error"
      : "ready";

  const returnPath = `/accept-invitation/?${new URLSearchParams({
    token: invitationToken,
  }).toString()}`;

  const loginPath = `/login?${new URLSearchParams({
    next: returnPath,
  }).toString()}`;

  const registerPath = `/register?${new URLSearchParams({
    next: returnPath,
  }).toString()}`;

  async function handleSwitchAccount() {
    if (isSwitchingAccount) return;

    setIsSwitchingAccount(true);
    setAccountError(null);

    saveInvitationReturn(returnPath);

    try {
      await logout();
      router.replace(loginPath);
    } catch {
      setAccountError("Unable to sign out. Please try again.");
      setIsSwitchingAccount(false);
    }
  }

  async function handleAccept() {
    if (!accessToken || !invitationToken || isSubmitting || result) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await acceptOrganizationInvitation(
        accessToken,
        invitationToken,
      );

      setResult(response);
      clearInvitationReturn();

      window.history.replaceState(
        window.history.state,
        "",
        "/accept-invitation/",
      );
    } catch (err) {
      if (err instanceof ApiError) {
        const tokenErrors = err.errors?.token;
        const emailErrors = err.errors?.email;
        const detailErrors = err.errors?.detail;

        const message = tokenErrors ?? emailErrors ?? detailErrors;

        setError(
          Array.isArray(message)
            ? message.join(" ")
            : typeof message === "string"
              ? message
              : err.message,
        );
      } else {
        setError("Unable to accept this invitation. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Brand />

        <section className={styles.card} aria-live="polite">
          <StatusIcon status={status} />

          {status === "success" && result ? (
            <>
              <h1>You joined {result.organization.name}.</h1>
              <p className={styles.description}>
                You are now a member of this organization.
                You can start collaborating with your team.
              </p>

              <Link
                className={styles.primaryButton}
                href={`/dashboard/organizations/${encodeURIComponent(
                  result.organization.slug,
                )}`}
              >
                Go to Workspace
              </Link>

              <Link
                className={styles.secondaryLink}
                href="/dashboard/organizations"
              >
                View all organizations
              </Link>
            </>
          ) : status === "error" ? (
            <>
              <h1>This invitation can&apos;t be used</h1>
              <p className={styles.description}>
                This invitation may be invalid, expired, revoked,
                or intended for another account.
              </p>

              <div className={styles.errorMessage} role="alert">
                {error ?? "The invitation link is missing or invalid."}
              </div>

              {isAuthenticated ? (
                <Link className={styles.primaryButton} href="/dashboard/organizations">
                  Go to organizations
                </Link>
              ) : (
                <Link className={styles.primaryButton} href={loginPath}>
                  Sign in with another account
                </Link>
              )}

              <Link
                className={styles.secondaryLink}
                href="/dashboard/organizations"
              >
                Go to organizations
              </Link>

              <p className={styles.helpText}>
                If the invitation has expired or was revoked,
                ask an organization admin to send a new one.
              </p>
            </>
          ) : (
            <>
              <h1>Accept your invitation</h1>

              <p className={styles.description}>
                You&apos;ve been invited to join an organization
                on TeamBoard. Accept the invitation to collaborate
                with your team.
              </p>

              {isLoading ? (
                <button className={styles.primaryButton} disabled>
                  Checking session...
                </button>
              ) : isAuthenticated ? (
                <>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    disabled={isSubmitting}
                    onClick={() => void handleAccept()}
                  >
                    {isSubmitting
                      ? "Accepting invitation..."
                      : "Accept invitation"}
                  </button>

                  {user && (
                    <p className={styles.accountHint}>
                      Signed in as {user.email}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <Link
                    className={styles.primaryButton}
                    href={loginPath}
                    onClick={() => saveInvitationReturn(returnPath)}
                  >
                    Sign in to accept
                  </Link>

                  <Link
                    className={styles.secondaryLink}
                    href={registerPath}
                    onClick={() => saveInvitationReturn(returnPath)}
                  >
                    Don&apos;t have an account? Sign up
                  </Link>
                </>
              )}

              {!isLoading && isAuthenticated && (
                <>
                  {accountError && (
                    <div className={styles.errorMessage} role="alert">
                      {accountError}
                    </div>
                  )}

                  <button
                    type="button"
                    className={styles.textButton}
                    disabled={isSwitchingAccount || isSubmitting}
                    onClick={() => void handleSwitchAccount()}
                  >
                    {isSwitchingAccount
                      ? "Switching account..."
                      : "Not you? Use another account"}
                  </button>
                </>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense
      fallback={
        <main className={styles.page}>
          <div className={styles.container}>
            <Brand />
            <div className={styles.card}>
              <p className={styles.description}>Loading invitation...</p>
            </div>
          </div>
        </main>
      }
    >
      <InvitationContent />
    </Suspense>
  );
}
