
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import AuthShell from "@/components/auth/AuthShell";
import PasswordField from "@/components/auth/PasswordField";
import Button from "@/components/ui/Button";
import { confirmPasswordReset } from "@/lib/api";

import styles from "./reset-password.module.css";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const requirements = [
    {
      label: "At least 8 characters",
      met: password.length >= 8,
    },
    {
      label: "Not entirely numeric",
      met: password.length > 0 && !/^\d+$/.test(password),
    },
    {
      label: "Passwords match",
      met: passwordConfirm.length > 0 && password === passwordConfirm,
    },
  ];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const uid = params.get("uid");
    const token = params.get("token");

    if (!uid || !token) {
      setError("This password reset link is invalid or incomplete.");
      return;
    }

    setLoading(true);

    try {
      const result = await confirmPasswordReset(
        uid,
        token,
        password,
        passwordConfirm,
      );

      setMessage(
        result.detail || "Your password has been reset successfully.",
      );
      setPassword("");
      setPasswordConfirm("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reset your password. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h2>Set a new password</h2>
        <p>
          Create a strong password for your account.
          It should be different from your previous password.
        </p>
      </div>

      {message ? (
        <div className={styles.completed}>
          <p className={styles.success} role="status">
            {message}
          </p>
          <Link href="/login" className={styles.submitLink}>
            Continue to sign in
          </Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit}>
          <PasswordField
            id="new-password"
            name="new-password"
            label="New password"
            placeholder="Enter a new password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <PasswordField
            id="confirm-password"
            name="confirm-password"
            label="Confirm new password"
            placeholder="Repeat your new password"
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            required
          />

          <div className={styles.requirements}>
            {requirements.map((requirement) => (
              <div
                key={requirement.label}
                className={`${styles.requirement} ${
                  requirement.met ? styles.met : ""
                }`}
              >
                <span aria-hidden="true">
                  {requirement.met ? "✓" : "○"}
                </span>
                {requirement.label}
              </div>
            ))}
          </div>

          {error && (
            <div className={styles.error} role="alert">
              {error}
            </div>
          )}

          <Button
            type="submit"
            className={styles.submit}
            loading={loading}
          >
            Reset password
          </Button>
        </form>
      )}

      {!message && (
        <Link href="/login" className={styles.backLink}>
          <span aria-hidden="true">←</span>
          Back to sign in
        </Link>
      )}
    </AuthShell>
  );
}
