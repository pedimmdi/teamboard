"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { setTokens } = useAuth();
  const router = useRouter();

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await login(email.trim(), password);
      const user = await getCurrentUser(data.access);

      setTokens(
        data.access,
        user,
      );
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
            <h2>Welcome back</h2>
            <p>Sign in to your TeamBoard account</p>
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

            <div className="password-field">
              <div className="password-label-row">
                <label htmlFor="password">Password</label>
                <Link href="/forgot-password">
                  Forgot password?
                </Link>
              </div>

              <input
                id="password"
                name="password"
                type="password"
                placeholder="Enter your password"
                autoComplete="current-password"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                required
              />
            </div>

            {error && (
              <div className="form-error" role="alert">
                {error}
                {error.toLowerCase().includes("not verified") && (
                  <>
                    {" "}
                    <Link href="/verify-email">
                      Verify your email
                    </Link>
                  </>
                )}
              </div>
            )}

            <Button
              type="submit"
              loading={loading}
              className="primary-button"
            >
              Sign in
            </Button>
          </form>

          <p className="auth-footer">
            Don&apos;t have an account?{" "}
            <Link
              href={getInvitationAuthUrl(
                "/register",
                typeof window === "undefined"
                  ? null
                  : new URLSearchParams(window.location.search).get("next"),
              )}
              onClick={() => {
                const params = new URLSearchParams(window.location.search);
                saveInvitationReturn(params.get("next"));
              }}
            >
              Create an account
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}