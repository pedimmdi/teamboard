
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import AuthShell from "@/components/auth/AuthShell";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { requestPasswordReset } from "@/lib/api";

import styles from "./forgot-password.module.css";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");
    setLoading(true);

    try {
      const result = await requestPasswordReset(email.trim());

      setMessage(
        result.detail ||
          "If an account exists for this email, a password reset link has been sent.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to request a password reset. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h2>Forgot your password?</h2>
        <p>
          Enter your email address and we&apos;ll send you a link
          to reset your password.
        </p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        <Input
          id="email"
          name="email"
          type="email"
          label="Email address"
          placeholder="you@example.com"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        {message && (
          <div className={styles.success} role="status">
            {message}
          </div>
        )}

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
          Send reset link
        </Button>
      </form>

      <Link href="/login" className={styles.backLink}>
        <span aria-hidden="true">←</span>
        Back to sign in
      </Link>
    </AuthShell>
  );
}
