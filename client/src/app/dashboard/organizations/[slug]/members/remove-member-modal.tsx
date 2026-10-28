
"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  removeOrganizationMember,
  type OrganizationMember,
} from "@/lib/api";

import styles from "./remove-member-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  member: OrganizationMember;
  onClose: () => void;
  onRemoved: () => void;
};

export default function RemoveMemberModal({
  accessToken,
  slug,
  member,
  onClose,
  onRemoved,
}: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        'button:not(:disabled)',
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

  async function handleRemove() {
    if (isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await removeOrganizationMember(
        accessToken,
        slug,
        member.id,
      );

      onRemoved();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to remove member.",
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
        aria-labelledby="remove-member-title"
        aria-describedby="remove-member-description"
        tabIndex={-1}
      >
        <h2 id="remove-member-title">Remove member</h2>

        <p
          id="remove-member-description"
          className={styles.description}
        >
          Are you sure you want to remove{" "}
          <strong>{member.user_email}</strong> from this organization?
        </p>

        <p className={styles.note}>
          This person will lose access to the organization.
          Their TeamBoard account will not be deleted.
        </p>

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
            className={styles.removeButton}
            disabled={isSubmitting}
            onClick={handleRemove}
          >
            {isSubmitting ? "Removing..." : "Remove member"}
          </button>
        </div>
      </div>
    </div>
  );
}
