
"use client";

import { useEffect, useRef, useState } from "react";

import styles from "./confirm-action-modal.module.css";

type Props = {
  title: string;
  description: string;
  confirmLabel: string;
  pendingLabel: string;
  workspaceName?: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

export default function ConfirmActionModal({
  title,
  description,
  confirmLabel,
  pendingLabel,
  workspaceName,
  onClose,
  onConfirm,
}: Props) {
  const [confirmation, setConfirmation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  const submittingRef = useRef(false);

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
        return;
      }

      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled)',
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

  const canConfirm =
    workspaceName === undefined ||
    confirmation === workspaceName;

  async function handleConfirm() {
    if (isSubmitting || !canConfirm) return;

    setIsSubmitting(true);
    submittingRef.current = true;
    setError(null);

    try {
      await onConfirm();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to complete this action.",
      );
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submittingRef.current) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-action-title"
        aria-describedby="confirm-action-description"
        tabIndex={-1}
      >
        <h2 id="confirm-action-title">{title}</h2>

        <p
          id="confirm-action-description"
          className={styles.description}
        >
          {description}
        </p>

        {workspaceName !== undefined && (
          <div className={styles.field}>
            <label htmlFor="confirm-workspace-name">
              Type <strong>{workspaceName}</strong> to confirm
            </label>

            <input
              id="confirm-workspace-name"
              type="text"
              value={confirmation}
              disabled={isSubmitting}
              autoComplete="off"
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </div>
        )}

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
            className={styles.dangerButton}
            disabled={!canConfirm || isSubmitting}
            onClick={() => void handleConfirm()}
          >
            {isSubmitting ? pendingLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
