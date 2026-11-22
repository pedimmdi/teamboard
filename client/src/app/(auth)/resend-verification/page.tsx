
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
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
  const { locale, t } = useLocale();
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
          : t("Unable to send a verification email. Please try again.", "ایمیل تأیید ارسال نشد. دوباره تلاش کنید."),
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
          title={t("Check your inbox", "صندوق ایمیل خود را بررسی کنید")}
          description={
            <>
              {t("If your account is eligible, a verification email has been sent to", "اگر حساب‌تان واجد شرایط باشد، ایمیل تأیید ارسال شده است به")}{" "}
              <strong><bdi>{email}</bdi></strong>.
            </>
          }
        >
          <Link href="/login" className={styles.primaryLink}>
            {t("Back to sign in", "بازگشت به ورود")}
          </Link>
        </VerificationStatus>
      ) : (
        <VerificationStatus
          tone="info"
          title={t("Send a new verification link", "پیوند تأیید جدید بگیرید")}
          description={t("Enter your email address and we'll send you another verification link.", "نشانی ایمیل‌تان را وارد کنید تا پیوند تأیید جدیدی بفرستیم.")}
        >
          <form
            className={styles.form}
            onSubmit={handleSubmit}
          >
            <Input
              id="email"
              name="email"
              type="email"
              label={t("Email address", "نشانی ایمیل")}
              placeholder="you@example.com"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />

            {error && (
              <div className={styles.error} role="alert">
                {localizeAccountMessage(locale, error, "ایمیل تأیید ارسال نشد. دوباره تلاش کنید.")}
              </div>
            )}

            <Button
              type="submit"
              className={styles.submit}
              loading={loading}
            >
              {t("Send verification email", "ارسال ایمیل تأیید")}
            </Button>
          </form>

          <Link
            href="/login"
            className={styles.secondaryLink}
          >
            {t("Back to sign in", "بازگشت به ورود")}
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
