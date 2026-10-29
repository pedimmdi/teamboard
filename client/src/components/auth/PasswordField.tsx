
"use client";

import { useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import styles from "./PasswordField.module.css";

type PasswordFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type"
> & {
  label: string;
  error?: string;
  action?: ReactNode;
};

export default function PasswordField({
  label,
  error,
  action,
  id,
  ...props
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label htmlFor={id}>{label}</label>
        {action}
      </div>

      <div className={styles.inputWrapper}>
        <input
          {...props}
          id={id}
          type={visible ? "text" : "password"}
          aria-invalid={Boolean(error)}
          aria-describedby={error && id ? `${id}-error` : undefined}
        />

        <button
          type="button"
          className={styles.toggle}
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
        >
          {visible ? (
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8" />
              <path d="M9.8 5.3A10.7 10.7 0 0 1 12 5c5 0 9 4.5 10 7a13 13 0 0 1-3.2 4.3M6.3 6.3C4.2 7.6 2.7 10 2 12c1 2.5 5 7 10 7 1.5 0 2.9-.4 4.1-1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>

      {error && (
        <p id={id ? `${id}-error` : undefined} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
