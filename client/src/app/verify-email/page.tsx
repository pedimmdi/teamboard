
"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { verifyEmail } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [message, setMessage] = useState("Verifying your email...");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!uid || !token) {
        setMessage("This verification link is invalid or incomplete.");
        setLoading(false);
        return;
      }

      try {
        const result = await verifyEmail(uid, token);

        if (!cancelled) {
          setMessage(result.detail);
          setSuccess(true);
        }
      } catch (error) {
        if (!cancelled) {
          const errorMessage =
            error instanceof Error ? error.message : "";

          if (errorMessage === "Email address is already verified.") {
            setMessage("Your email address is already verified. You can log in.");
            setSuccess(true);
          } else {
            setMessage(
              errorMessage || "Email verification failed. Please try again.",
            );
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void verify();

    return () => {
      cancelled = true;
    };
  }, [uid, token]);

  return (
    <main className="auth-page">
      <section className="auth-brand-panel">
        <div className="brand-content">
          <div className="brand-mark">T</div>
          <h1>TeamBoard</h1>
          <p>Manage your team, projects, and work in one place.</p>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-header">
            <h2>
              {loading
                ? "Verifying your email"
                : success
                  ? "Email verified"
                  : "Verification unsuccessful"}
            </h2>
            <p>{message}</p>
          </div>

          {!loading && (
            <div className="auth-footer">
              {success ? (
                <Link href="/login">Continue to login</Link>
              ) : (
                <Link href="/register">Back to registration</Link>
              )}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <main className="auth-page">
          <section className="auth-form-panel">
            <div className="auth-card">
              <p>Loading verification page...</p>
            </div>
          </section>
        </main>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
