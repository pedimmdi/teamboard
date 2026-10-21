"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { requestPasswordReset } from "@/lib/api";

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
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="brand-content">
          <div className="brand-mark">T</div>
          <h1>TeamBoard</h1>
          <p>Get back to work with your team.</p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-header">
            <h2>Forgot password?</h2>
            <p>Enter your email and we’ll send you a reset link.</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            <Input
              id="email"
              name="email"
              type="email"
              label="Email"
              placeholder="you@example.com"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />

            {message && (
              <div role="status" className="form-success">
                {message}
              </div>
            )}

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
              Send reset link
            </Button>
          </form>

          <p className="auth-footer">
            Remember your password? <Link href="/login">Sign in</Link>
          </p>
        </div>
      </section>
    </main>
  );
}