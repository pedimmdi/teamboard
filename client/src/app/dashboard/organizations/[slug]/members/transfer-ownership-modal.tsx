
"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  transferOrganizationOwnership,
  type OrganizationMember,
} from "@/lib/api";

import styles from "./transfer-ownership-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  member: OrganizationMember;
  onClose: () => void;
  onTransferred: () => void;
};

export default function TransferOwnershipModal({
  accessToken,
  slug,
  member,
  onClose,
  onTransferred,
}: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
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
    dialogRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submittingRef.current) {
        closeRef.current();
      }

      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled)',
      );

      if (!focusable?.length) return;

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

  async function handleTransfer() {
    if (isSubmitting || !confirmed) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await transferOrganizationOwnership(
        accessToken,
        slug,
        member.id,
      );

      onTransferred();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to transfer ownership.",
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
        aria-labelledby="transfer-title"
        aria-describedby="transfer-description"
        tabIndex={-1}
      >
        <h2 id="transfer-title">Transfer ownership</h2>

        <p id="transfer-description" className={styles.description}>
          You are about to transfer ownership of this organization to
          <strong> {member.user_email}</strong>.
        </p>

        <div className={styles.warning}>
          The selected member will become the new owner.
          Your role will change to Admin, and you will lose
          owner-only permissions.
        </div>

        <label className={styles.confirmation}>
          <input
            type="checkbox"
            checked={confirmed}
            disabled={isSubmitting}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          <span>I understand the consequences of this transfer.</span>
        </label>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.cancelButton}
            disabled={isSubmitting}
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            type="button"
            className={styles.transferButton}
            disabled={!confirmed || isSubmitting}
            onClick={handleTransfer}
          >
            {isSubmitting ? "Transferring..." : "Transfer ownership"}
          </button>
        </div>
      </div>
    </div>
  );
}
