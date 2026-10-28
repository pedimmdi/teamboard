
"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  revokeOrganizationInvitation,
  type OrganizationInvitation,
} from "@/lib/api";

import styles from "./revoke-invitation-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  invitation: OrganizationInvitation;
  onClose: () => void;
  onRevoked: () => void;
};

export default function RevokeInvitationModal({
  accessToken,
  slug,
  invitation,
  onClose,
  onRevoked,
}: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef(onClose);
  const submittingRef = useRef(isSubmitting);

  useEffect(() => {
    closeRef.current = onClose;
    submittingRef.current = isSubmitting;
  }, [onClose, isSubmitting]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement as HTMLElement | null;

    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submittingRef.current) {
        closeRef.current();
        return;
      }

      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled)",
      );

      if (!focusable?.length) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, []);

  async function handleRevoke() {
    if (isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await revokeOrganizationInvitation(
        accessToken,
        slug,
        invitation.id,
      );

      onRevoked();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to revoke invitation.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="revoke-title"
        aria-describedby="revoke-description"
      >
        <h2 id="revoke-title">Revoke invitation?</h2>

        <p id="revoke-description" className={styles.description}>
          The invitation sent to{" "}
          <strong>{invitation.email}</strong>{" "}
          will no longer be valid.
        </p>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <div className={styles.actions}>
          <button
            ref={cancelRef}
            type="button"
            className={styles.cancelButton}
            disabled={isSubmitting}
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            type="button"
            className={styles.revokeButton}
            disabled={isSubmitting}
            onClick={handleRevoke}
          >
            {isSubmitting ? "Revoking..." : "Revoke invitation"}
          </button>
        </div>
      </div>
    </div>
  );
}
