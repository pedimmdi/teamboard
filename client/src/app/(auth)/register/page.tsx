
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import AuthShell from "@/components/auth/AuthShell";
import PasswordField from "@/components/auth/PasswordField";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { ApiError, register } from "@/lib/api";
import {
  getInvitationAuthUrl,
  getSafeInvitationReturn,
  readInvitationReturn,
  saveInvitationReturn,
} from "@/lib/invitation-return";

import VerificationShell from "@/components/auth/VerificationShell";
import VerificationStatus from "@/components/auth/VerificationStatus";

import styles from "./register.module.css";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const requirements = [
    { label: "At least 8 characters", met: password.length >= 8 },
    {
      label: "Not entirely numeric",
      met: password.length > 0 && !/^\d+$/.test(password),
    },
    {
      label: "Passwords match",
      met: passwordConfirm.length > 0 && password === passwordConfirm,
    },
  ];

  function getLoginPath() {
    const params = new URLSearchParams(window.location.search);
    const returnPath =
      getSafeInvitationReturn(params.get("next")) ??
      readInvitationReturn();

    if (returnPath) saveInvitationReturn(returnPath);

    return getInvitationAuthUrl("/login", returnPath);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
      await register(email.trim(), password, passwordConfirm);
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
            (Object.keys(errors).length === 0 ? err.message : ""),
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
      <VerificationShell>
        <VerificationStatus
          tone="info"
          title="Check your inbox"
          description={
            <>
              We&apos;ve sent a verification link to{" "}
              <strong>{email}</strong>.
              <br />
              Open the link in your email to activate your account.
            </>
          }
        >
          <Link
            href={`/resend-verification?${new URLSearchParams({
              email: email.trim(),
            }).toString()}`}
            className={styles.verificationButton}
          >
            Resend verification email
          </Link>

          <Link
            href="/login"
            className={styles.verificationLink}
            onClick={() => {
              const params = new URLSearchParams(window.location.search);
              saveInvitationReturn(params.get("next"));
            }}
          >
            Already verified? Sign in
          </Link>
        </VerificationStatus>
      </VerificationShell>
    );
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h2>Create your account</h2>
        <p>Join TeamBoard and start working with your team.</p>
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
          error={fieldErrors.email}
          required
        />

        <PasswordField
          id="password"
          name="password"
          label="Password"
          placeholder="Create a password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldErrors.password}
          required
        />

        <PasswordField
          id="password-confirm"
          name="password-confirm"
          label="Confirm password"
          placeholder="Repeat your password"
          autoComplete="new-password"
          value={passwordConfirm}
          onChange={(event) => setPasswordConfirm(event.target.value)}
          error={fieldErrors.password_confirm}
          required
        />

        <div className={styles.requirements}>
          {requirements.map((item) => (
            <div
              className={`${styles.requirement} ${
                item.met ? styles.met : ""
              }`}
              key={item.label}
            >
              <span aria-hidden="true">{item.met ? "✓" : "○"}</span>
              {item.label}
            </div>
          ))}
        </div>

        {error && (
          <div className={styles.errorBanner} role="alert">
            {error}
          </div>
        )}

        <Button
          type="submit"
          loading={loading}
          className={styles.submit}
        >
          Create account
        </Button>
      </form>

      <p className={styles.footer}>
        Already have an account?{" "}
        <Link
          href="/login"
          onClick={(event) => {
            event.preventDefault();
            window.location.assign(getLoginPath());
          }}
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
