"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import { confirmPasswordReset } from "@/lib/api";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

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
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="brand-content">
          <div className="brand-mark">T</div>
          <h1>TeamBoard</h1>
          <p>Secure access to your team workspace.</p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-header">
            <h2>Reset password</h2>
            <p>Choose a new password for your account.</p>
          </div>

          {message ? (
            <>
              <p role="status" className="form-success">
                {message}
              </p>
              <p className="auth-footer">
                <Link href="/login">Continue to sign in</Link>
              </p>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="password-field">
                <label htmlFor="password">New password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>

              <div className="password-field">
                <label htmlFor="password-confirm">
                  Confirm new password
                </label>
                <input
                  id="password-confirm"
                  name="password-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={passwordConfirm}
                  onChange={(event) =>
                    setPasswordConfirm(event.target.value)
                  }
                  required
                />
              </div>

              {error && (
                <div role="alert" className="form-error">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                loading={loading}
                className="primary-button"
              >
                Reset password
              </Button>
            </form>
          )}

          {!message && (
            <p className="auth-footer">
              <Link href="/login">Back to sign in</Link>
            </p>
          )}
        </div>
      </section>
    </main>
  );
}