
"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AuthShell from "@/components/auth/AuthShell";
import PasswordField from "@/components/auth/PasswordField";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { ApiError, getCurrentUser, login } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  clearInvitationReturn,
  getInvitationAuthUrl,
  getSafeInvitationReturn,
  readInvitationReturn,
  saveInvitationReturn,
} from "@/lib/invitation-return";

import styles from "./login.module.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { setTokens } = useAuth();
  const router = useRouter();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await login(email.trim(), password);
      const user = await getCurrentUser(data.access);

      setTokens(data.access, user);

      const params = new URLSearchParams(window.location.search);
      const returnPath =
        getSafeInvitationReturn(params.get("next")) ??
        readInvitationReturn();

      if (returnPath) {
        saveInvitationReturn(returnPath);
      } else {
        clearInvitationReturn();
      }

      router.replace(returnPath ?? "/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  function getRegisterPath() {
    const params = new URLSearchParams(window.location.search);
    const returnPath =
      getSafeInvitationReturn(params.get("next")) ??
      readInvitationReturn();

    if (returnPath) saveInvitationReturn(returnPath);

    return getInvitationAuthUrl("/register", returnPath);
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h2>Welcome back</h2>
        <p>Sign in to your TeamBoard account.</p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        {error && (
          <div className={styles.errorBanner} role="alert">
            <span aria-hidden="true">!</span>
            <p>{error}</p>
          </div>
        )}

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

        <PasswordField
          id="password"
          name="password"
          label="Password"
          placeholder="Enter your password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          action={<Link href="/forgot-password">Forgot password?</Link>}
          required
        />

        <Button
          type="submit"
          loading={loading}
          className={styles.submit}
        >
          Sign in
        </Button>
      </form>

      <p className={styles.footer}>
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          onClick={(event) => {
            event.preventDefault();
            router.push(getRegisterPath());
          }}
        >
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}
