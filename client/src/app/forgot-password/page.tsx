"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { requestPasswordReset } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      await requestPasswordReset(email);
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.",
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

          <p>
            Manage your team, projects, and work in one place.
          </p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          {!submitted ? (
            <>
              <div className="auth-header">
                <h2>Forgot your password?</h2>

                <p>
                  Enter your email and we&apos;ll send you a
                  password reset link.
                </p>
              </div>

              <form
                className="auth-form"
                onSubmit={handleSubmit}
              >
                <Input
                  id="email"
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(event.target.value)
                  }
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />

                {error && (
                  <p className="form-error">{error}</p>
                )}

                <Button
                  type="submit"
                  className="primary-button"
                  loading={loading}
                >
                  Send reset link
                </Button>
              </form>

              <div className="auth-footer">
                <Link href="/login">
                  Back to login
                </Link>
              </div>
            </>
          ) : (
            <>
              <div className="auth-header">
                <h2>Check your email</h2>

                <p>
                  If an account exists for{" "}
                  <strong>{email}</strong>, password reset
                  instructions have been sent.
                </p>
              </div>

              <div className="auth-footer">
                <Link href="/login">
                  Back to login
                </Link>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}