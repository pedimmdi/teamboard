
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import VerificationShell from "@/components/auth/VerificationShell";
import VerificationStatus from "@/components/auth/VerificationStatus";
import { verifyEmail } from "@/lib/api";

import styles from "./verify-email.module.css";

type VerificationState = "loading" | "success" | "error";

const verificationRequests = new Map<
  string,
  ReturnType<typeof verifyEmail>
>();

function verifyEmailOnce(uid: string, token: string) {
  const key = JSON.stringify([uid, token]);
  const existing = verificationRequests.get(key);

  if (existing) return existing;

  const request = verifyEmail(uid, token);
  verificationRequests.set(key, request);

  return request;
}

export default function VerifyEmailPage() {
  const [status, setStatus] = useState<VerificationState>("loading");
  const [message, setMessage] = useState(
    "We're checking your verification link.",
  );

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      const params = new URLSearchParams(window.location.search);
      const uid = params.get("uid");
      const token = params.get("token");

      if (!uid || !token) {
        setMessage("This verification link is missing or invalid.");
        setStatus("error");
        return;
      }

      try {
        const result = await verifyEmailOnce(uid, token);

        if (cancelled) return;

        setMessage(result.detail || "Your email has been verified.");
        setStatus("success");

        window.history.replaceState(
          window.history.state,
          "",
          "/verify-email",
        );
      } catch (error) {
        if (cancelled) return;

        setMessage(
          error instanceof Error
            ? error.message
            : "This verification link is invalid or has expired.",
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
    <VerificationShell>
      {status === "loading" ? (
        <VerificationStatus
          tone="info"
          title="Verifying your email"
          description={message}
        >
          <p className={styles.loadingText}>Please wait...</p>
        </VerificationStatus>
      ) : status === "success" ? (
        <VerificationStatus
          tone="success"
          title="Email verified"
          description="Your email address is verified. Your account is ready to use."
        >
          <Link href="/login" className={styles.primaryButton}>
            Continue to sign in
          </Link>
        </VerificationStatus>
      ) : (
        <VerificationStatus
          tone="error"
          title="Verification link expired"
          description={message}
        >
          <Link href="/resend-verification" className={styles.primaryButton}>
            Send a new link
          </Link>

          <Link href="/login" className={styles.secondaryLink}>
            Back to sign in
          </Link>
        </VerificationStatus>
      )}
    </VerificationShell>
  );
}
