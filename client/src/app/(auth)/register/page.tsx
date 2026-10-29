"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import {
  ApiError,
  register,
} from "@/lib/api";
import {
  saveInvitationReturn,
} from "@/lib/invitation-return";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, string>
  >({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setFieldErrors({});

    const params = new URLSearchParams(window.location.search);

    saveInvitationReturn(params.get("next"));

    if (password !== passwordConfirm) {
      setFieldErrors({
        password_confirm: "Passwords do not match.",
      });
      return;
    }

    setLoading(true);

    try {
      await register(
        email.trim(),
        password,
        passwordConfirm,
      );

      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        const errors = err.errors ?? {};

        setFieldErrors({
          email:
            typeof errors.email === "string"
              ? errors.email
              : errors.email?.[0] ?? "",
          password:
            typeof errors.password === "string"
              ? errors.password
              : errors.password?.[0] ?? "",
          password_confirm:
            typeof errors.password_confirm === "string"
              ? errors.password_confirm
              : errors.password_confirm?.[0] ?? "",
        });

        const nonFieldError =
          typeof errors.non_field_errors === "string"
            ? errors.non_field_errors
            : errors.non_field_errors?.[0];

        setError(
          nonFieldError ||
            (Object.keys(errors).length === 0
              ? err.message
              : ""),
        );
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to create your account.",
        );
      }
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
              Organize your work and collaborate with
              your team.
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
              <Link
                href="/login"
                onClick={() => {
                  const params = new URLSearchParams(window.location.search);
                  saveInvitationReturn(params.get("next"));
                }}
              >
                Sign in
              </Link>
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

          <form
            onSubmit={handleSubmit}
            className="auth-form"
          >
            <Input
              id="email"
              name="email"
              type="email"
              label="Email"
              placeholder="you@example.com"
              autoComplete="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
            />

            {fieldErrors.email && (
              <div className="form-error">
                {fieldErrors.email}
              </div>
            )}

            <Input
              id="password"
              name="password"
              type="password"
              label="Password"
              placeholder="Create a password"
              autoComplete="new-password"
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              required
            />

            {fieldErrors.password && (
              <div className="form-error">
                {fieldErrors.password}
              </div>
            )}

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

            {fieldErrors.password_confirm && (
              <div className="form-error">
                {fieldErrors.password_confirm}
              </div>
            )}

            {error && (
              <div className="form-error">{error}</div>
            )}

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
            <Link
              href="/login"
              onClick={() => {
                const params = new URLSearchParams(window.location.search);
                saveInvitationReturn(params.get("next"));
              }}
            >
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}