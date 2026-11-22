
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { useEffect, useId, useRef, useState } from "react";
import {
  ApiError,
  createWorkspace,
  type Workspace,
} from "@/lib/api";

import styles from "./create-workspace-modal.module.css";

type Props = {
  accessToken: string;
  onClose: () => void;
  onCreated: (workspace: Workspace) => void;
};

export default function CreateWorkspaceModal({
  accessToken,
  onClose,
  onCreated,
}: Props) {
  const { locale, t } = useLocale();
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
      setError(t("Workspace name is required.", "نام فضای کاری را وارد کنید."));
      inputRef.current?.focus();
      return;
    }

    if (trimmedName.length > 150) {
      setError(t("Workspace name must be 150 characters or fewer.", "نام فضای کاری باید حداکثر ۱۵۰ نویسه باشد."));
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const workspace = await createWorkspace(accessToken, {
        name: trimmedName,
      });

      onCreated(workspace);
    } catch (err) {
      if (err instanceof ApiError) {
        const nameError = err.errors?.name;
        const message = Array.isArray(nameError)
          ? nameError[0]
          : nameError;

        setError(message || err.message);
      } else {
        setError(t("Unable to create workspace. Please try again.", "فضای کاری ایجاد نشد. دوباره تلاش کنید."));
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
            <h2 id={titleId}>{t("Create workspace", "ایجاد فضای کاری")}</h2>
            <p id={descriptionId}>
              {t("Workspaces help you organize your work and collaborate with your team.", "با فضای کاری کارها را مرتب کنید و با تیمتان همکاری کنید.")}
            </p>
          </div>

          <button
            type="button"
            className={styles.closeButton}
            aria-label={t("Close dialog", "بستن پنجره")}
            onClick={onClose}
            disabled={isSubmitting}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label htmlFor={nameId}>{t("Workspace name", "نام فضای کاری")}</label>
            <input
              ref={inputRef}
              id={nameId}
              type="text"
              value={name}
              maxLength={150}
              placeholder={t("e.g. Acme Inc.", "برای نمونه، تیم طراحی")}
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
                {localizeAccountMessage(locale, error, "فضای کاری ایجاد نشد. دوباره تلاش کنید.")}
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
              {t("Cancel", "انصراف")}
            </button>

            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? t("Creating...", "در حال ایجاد…") : t("Create workspace", "ایجاد فضای کاری")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
