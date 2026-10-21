"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { verifyEmail } from "@/lib/api";

type VerificationStatus = "loading" | "success" | "error";

export default function VerifyEmailPage() {
  const [status, setStatus] =
    useState<VerificationStatus>("loading");
  const [message, setMessage] = useState(
    "Verifying your email address...",
  );

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      const params = new URLSearchParams(
        window.location.search,
      );
      const uid = params.get("uid");
      const token = params.get("token");

      if (!uid || !token) {
        setMessage("The verification link is invalid.");
        setStatus("error");
        return;
      }

      try {
        const result = await verifyEmail(uid, token);

        if (cancelled) return;

        setMessage(
          result.detail || "Your email has been verified.",
        );
        setStatus("success");
      } catch (error) {
        if (cancelled) return;

        setMessage(
          error instanceof Error
            ? error.message
            : "Email verification failed.",
        );
        setStatus("error");
      }
    }

    void verify();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="brand-content">
          <div className="brand-mark">T</div>
          <h1>TeamBoard</h1>
          <p>Secure your account and get started.</p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-header">
            <h2>
              {status === "loading"
                ? "Verifying your email"
                : status === "success"
                  ? "Email verified"
                  : "Verification failed"}
            </h2>

            <p role="status">{message}</p>
          </div>

          {status !== "loading" && (
            <p className="auth-footer">
              <Link href="/login">
                Go to sign in
              </Link>
            </p>
          )}
        </div>
      </section>
    </main>
  );
}