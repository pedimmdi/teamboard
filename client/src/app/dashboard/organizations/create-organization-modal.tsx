
"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  ApiError,
  createOrganization,
  type Organization,
} from "@/lib/api";

import styles from "./create-organization-modal.module.css";

type Props = {
  accessToken: string;
  onClose: () => void;
  onCreated: (organization: Organization) => void;
};

export default function CreateOrganizationModal({
  accessToken,
  onClose,
  onCreated,
}: Props) {
  const titleId = useId();
  const descriptionId = useId();
  const nameId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    inputRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }

      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled])'
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
    };
  }, [onClose]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) return;

    const trimmedName = name.trim();

    if (!trimmedName) {
      setError("Organization name is required.");
      inputRef.current?.focus();
      return;
    }

    if (trimmedName.length > 150) {
      setError("Organization name must be 150 characters or fewer.");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const organization = await createOrganization(accessToken, {
        name: trimmedName,
      });

      onCreated(organization);
    } catch (err) {
      if (err instanceof ApiError) {
        const nameError = err.errors?.name;
        const message = Array.isArray(nameError)
          ? nameError[0]
          : nameError;

        setError(message || err.message);
      } else {
        setError("Unable to create organization. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className={styles.backdrop}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <div className={styles.heading}>
          <div>
            <h2 id={titleId}>Create organization</h2>
            <p id={descriptionId}>
              Organizations help you organize your work and collaborate
              with your team.
            </p>
          </div>

          <button
            type="button"
            className={styles.closeButton}
            aria-label="Close dialog"
            onClick={onClose}
            disabled={isSubmitting}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label htmlFor={nameId}>Organization name</label>
            <input
              ref={inputRef}
              id={nameId}
              type="text"
              value={name}
              maxLength={150}
              placeholder="e.g. Acme Inc."
              autoComplete="off"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? `${nameId}-error` : undefined}
              disabled={isSubmitting}
              onChange={(event) => {
                setName(event.target.value);
                if (error) setError(null);
              }}
            />
            {error && (
              <p id={`${nameId}-error`} className={styles.error} role="alert">
                {error}
              </p>
            )}
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>

            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating..." : "Create organization"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
