
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
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
  const { locale, t } = useLocale();
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
          t("Unable to verify your email. Please try again.", "تأیید ایمیل انجام نشد. دوباره تلاش کنید."),
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
          title={t("Email verified", "ایمیل تأیید شد")}
          description={t("Your email address is verified. Your account is ready to use.", "نشانی ایمیل‌تان تأیید شد. حسابتان آماده استفاده است.")}
        >
          <Link href="/login" className={styles.primaryButton}>
            {t("Continue to sign in", "رفتن به صفحه ورود")}
          </Link>
        </VerificationStatus>
      ) : hasError ? (
        <VerificationStatus
          tone="error"
          title={t("Unable to verify email", "تأیید ایمیل انجام نشد")}
          description={
            missingParams
              ? t("This verification link is missing or invalid.", "پیوند تأیید ناقص یا نامعتبر است.")
              : localizeAccountMessage(locale, message, "تأیید ایمیل انجام نشد. دوباره تلاش کنید.")
          }
        >
          {!missingParams && (
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => setStatus("ready")}
            >
              {t("Try again", "تلاش دوباره")}
            </button>
          )}

          <Link
            href="/resend-verification"
            className={styles.secondaryLink}
          >
            {t("Send a new link", "ارسال پیوند جدید")}
          </Link>

          <Link href="/login" className={styles.secondaryLink}>
            {t("Back to sign in", "بازگشت به ورود")}
          </Link>
        </VerificationStatus>
      ) : (
        <VerificationStatus
          tone="info"
          title={t("Verify your email", "ایمیل‌تان را تأیید کنید")}
          description={t("Confirm your email address to activate your TeamBoard account.", "نشانی ایمیل‌تان را تأیید کنید تا حساب تیم‌بورد شما فعال شود.")}
        >
          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => void handleVerify()}
            disabled={status === "loading"}
          >
            {status === "loading" ? t("Verifying...", "در حال تأیید…") : t("Verify email", "تأیید ایمیل")}
          </button>

          <Link href="/login" className={styles.secondaryLink}>
            {t("Back to sign in", "بازگشت به ورود")}
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
