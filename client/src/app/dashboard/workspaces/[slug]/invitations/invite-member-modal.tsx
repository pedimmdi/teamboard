
"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  ApiError,
  createWorkspaceInvitation,
} from "@/lib/api";

import styles from "./invite-member-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  onClose: () => void;
  onInvited: () => void;
};

export default function InviteMemberModal({
  accessToken,
  slug,
  onClose,
  onInvited,
}: Props) {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
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
    emailRef.current?.focus();

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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) return;

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setError("Email address is required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await createWorkspaceInvitation(
        accessToken,
        slug,
        normalizedEmail,
      );

      onInvited();
    } catch (err) {
      if (err instanceof ApiError) {
        const emailErrors = err.errors?.email;

        if (Array.isArray(emailErrors)) {
          setError(emailErrors.join(" "));
        } else if (typeof emailErrors === "string") {
          setError(emailErrors);
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to send invitation.");
      }
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
        aria-labelledby="invite-title"
        aria-describedby="invite-description"
        tabIndex={-1}
      >
        <div className={styles.header}>
          <h2 id="invite-title">Invite member</h2>

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

        <p id="invite-description" className={styles.description}>
          Send an invitation to join your workspace.
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="invitation-email" className={styles.label}>
            Email address
          </label>

          <input
            ref={emailRef}
            id="invitation-email"
            type="email"
            className={styles.input}
            placeholder="person@example.com"
            value={email}
            disabled={isSubmitting}
            required
            maxLength={254}
            autoComplete="email"
            onChange={(event) => {
              setEmail(event.target.value);
              if (error) setError(null);
            }}
          />

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
              disabled={isSubmitting || !email.trim()}
            >
              {isSubmitting ? "Sending..." : "Send invitation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
