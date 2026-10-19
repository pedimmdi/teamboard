"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");

    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await register(email, password, passwordConfirm);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create your account.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <main className="auth-page">
        <section className="auth-brand-panel">
          <div className="brand-content">
            <div className="brand-mark">T</div>
            <h1>TeamBoard</h1>
            <p>
              Organize your work and collaborate with your team.
            </p>
          </div>
        </section>

        <section className="auth-form-panel">
          <div className="auth-card">
            <div className="auth-header">
              <h2>Check your email</h2>
              <p>
                We&apos;ve sent a verification link to{" "}
                <strong>{email}</strong>.
              </p>
            </div>

            <p className="auth-footer">
              Already verified?{" "}
              <Link href="/login">Sign in</Link>
            </p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="brand-content">
          <div className="brand-mark">T</div>

          <h1>TeamBoard</h1>

          <p>
            Organize your work, collaborate with your team,
            and keep everything in one place.
          </p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-header">
            <h2>Create your account</h2>
            <p>Get started with TeamBoard</p>
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

            <Input
              id="password"
              name="password"
              type="password"
              label="Password"
              placeholder="Create a password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            <Input
              id="password-confirm"
              name="password-confirm"
              type="password"
              label="Confirm password"
              placeholder="Repeat your password"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(event) =>
                setPasswordConfirm(event.target.value)
              }
              required
            />

            {error && <div className="form-error">{error}</div>}

            <Button
              type="submit"
              loading={loading}
              className="primary-button"
            >
              Create account
            </Button>
          </form>

          <p className="auth-footer">
            Already have an account?{" "}
            <Link href="/login">Sign in</Link>
          </p>
        </div>
      </section>
    </main>
  );
}