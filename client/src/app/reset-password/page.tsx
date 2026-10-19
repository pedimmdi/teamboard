"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import { confirmPasswordReset } from "@/lib/api";

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();

  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");

    if (!uid || !token) {
      setError("This password reset link is invalid.");
      return;
    }

    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await confirmPasswordReset(
        uid,
        token,
        password,
        passwordConfirm,
      );

      setSuccess(true);
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
          {!success ? (
            <>
              <div className="auth-header">
                <h2>Reset your password</h2>

                <p>
                  Choose a new password for your TeamBoard
                  account.
                </p>
              </div>

              <form
                className="auth-form"
                onSubmit={handleSubmit}
              >
                <Input
                  id="password"
                  label="New password"
                  type="password"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  autoComplete="new-password"
                  required
                />

                <Input
                  id="password-confirm"
                  label="Confirm password"
                  type="password"
                  value={passwordConfirm}
                  onChange={(event) =>
                    setPasswordConfirm(event.target.value)
                  }
                  autoComplete="new-password"
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
                  Reset password
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="auth-header">
                <h2>Password reset successful</h2>

                <p>
                  Your password has been changed successfully.
                  You can now log in with your new password.
                </p>
              </div>

              <div className="auth-footer">
                <Link href="/login">
                  Continue to login
                </Link>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}