
"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import VerificationShell from "@/components/auth/VerificationShell";
import VerificationStatus from "@/components/auth/VerificationStatus";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { resendVerificationEmail } from "@/lib/api";

import styles from "./resend-verification.module.css";

function ResendVerificationContent() {
  const searchParams = useSearchParams();

  const [email, setEmail] = useState(
    () => searchParams.get("email") ?? "",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      await resendVerificationEmail(email.trim());
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to send a verification email. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <VerificationShell>
      {success ? (
        <VerificationStatus
          tone="info"
          title="Check your inbox"
          description={
            <>
              If your account is eligible, a verification email
              has been sent to <strong>{email}</strong>.
            </>
          }
        >
          <Link href="/login" className={styles.primaryLink}>
            Back to sign in
          </Link>
        </VerificationStatus>
      ) : (
        <VerificationStatus
          tone="info"
          title="Send a new verification link"
          description="Enter your email address and we'll send you another verification link."
        >
          <form
            className={styles.form}
            onSubmit={handleSubmit}
          >
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

            {error && (
              <div className={styles.error} role="alert">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className={styles.submit}
              loading={loading}
            >
              Send verification email
            </Button>
          </form>

          <Link
            href="/login"
            className={styles.secondaryLink}
          >
            Back to sign in
          </Link>
        </VerificationStatus>
      )}
    </VerificationShell>
  );
}

export default function ResendVerificationPage() {
  return (
    <Suspense fallback={null}>
      <ResendVerificationContent />
    </Suspense>
  );
}
