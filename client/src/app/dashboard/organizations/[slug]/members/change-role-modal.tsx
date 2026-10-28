
"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  updateOrganizationMemberRole,
  type OrganizationMember,
} from "@/lib/api";

import styles from "./change-role-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  member: OrganizationMember;
  onClose: () => void;
  onUpdated: () => void;
};

export default function ChangeRoleModal({
  accessToken,
  slug,
  member,
  onClose,
  onUpdated,
}: Props) {
  const [role, setRole] = useState<"admin" | "member">(
    member.role === "admin" ? "admin" : "member",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (!isSubmitting) onClose();
      }

      if (event.key === "Tab") {
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), select:not(:disabled)',
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
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSubmitting, onClose]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting || role === member.role) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await updateOrganizationMemberRole(
        accessToken,
        slug,
        member.id,
        role,
      );
      onUpdated();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to update member role.",
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
        aria-labelledby="change-role-title"
      >
        <div className={styles.header}>
          <h2 id="change-role-title">Change member role</h2>
          <button
            type="button"
            className={styles.closeButton}
            aria-label="Close"
            disabled={isSubmitting}
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <p className={styles.description}>
          Update the role for <strong>{member.user_email}</strong>.
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="member-role" className={styles.label}>
            Role
          </label>

          <select
            id="member-role"
            className={styles.select}
            value={role}
            disabled={isSubmitting}
            onChange={(event) =>
              setRole(event.target.value as "admin" | "member")
            }
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>

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
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting || role === member.role}
            >
              {isSubmitting ? "Saving..." : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
