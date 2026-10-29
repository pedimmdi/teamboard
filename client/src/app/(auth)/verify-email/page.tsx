
"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import VerificationShell from "@/components/auth/VerificationShell";
import VerificationStatus from "@/components/auth/VerificationStatus";
import { ApiError, verifyEmail } from "@/lib/api";

import styles from "./verify-email.module.css";

type VerificationState = "ready" | "loading" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [status, setStatus] = useState<VerificationState>("ready");
  const [message, setMessage] = useState("");

  const missingParams = !uid || !token;
  const hasError = missingParams || status === "error";

  async function handleVerify() {
    if (!uid || !token || status !== "ready") {
      return;
    }

    setStatus("loading");
    setMessage("");

    try {
      await verifyEmail(uid, token);

      setStatus("success");

      window.history.replaceState(
        window.history.state,
        "",
        "/verify-email",
      );
    } catch (error) {
      if (error instanceof ApiError) {
        const detail = error.errors?.detail;
        const tokenError = error.errors?.token;
        const uidError = error.errors?.uid;
        const serverMessage = detail ?? tokenError ?? uidError;

        setMessage(
          typeof serverMessage === "string"
            ? serverMessage
            : Array.isArray(serverMessage)
              ? serverMessage.join(" ")
              : error.message,
        );
      } else {
        setMessage(
          "Unable to verify your email. Please try again.",
        );
      }

      setStatus("error");
    }
  }

  return (
    <VerificationShell>
      {status === "success" ? (
        <VerificationStatus
          tone="success"
          title="Email verified"
          description="Your email address is verified. Your account is ready to use."
        >
          <Link href="/login" className={styles.primaryButton}>
            Continue to sign in
          </Link>
        </VerificationStatus>
      ) : hasError ? (
        <VerificationStatus
          tone="error"
          title="Unable to verify email"
          description={
            missingParams
              ? "This verification link is missing or invalid."
              : message
          }
        >
          {!missingParams && (
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => setStatus("ready")}
            >
              Try again
            </button>
          )}

          <Link
            href="/resend-verification"
            className={styles.secondaryLink}
          >
            Send a new link
          </Link>

          <Link href="/login" className={styles.secondaryLink}>
            Back to sign in
          </Link>
        </VerificationStatus>
      ) : (
        <VerificationStatus
          tone="info"
          title="Verify your email"
          description="Confirm your email address to activate your TeamBoard account."
        >
          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => void handleVerify()}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Verifying..." : "Verify email"}
          </button>

          <Link href="/login" className={styles.secondaryLink}>
            Back to sign in
          </Link>
        </VerificationStatus>
      )}
    </VerificationShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
