
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { FormEvent, useState } from "react";
import Link from "next/link";

import AuthShell from "@/components/auth/AuthShell";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { requestPasswordReset } from "@/lib/api";

import styles from "./forgot-password.module.css";

export default function ForgotPasswordPage() {
  const { locale, t } = useLocale();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");
    setLoading(true);

    try {
      const result = await requestPasswordReset(email.trim());

      setMessage(
        (locale === "en" && result.detail) ||
          t("If an account exists for this email, a password reset link has been sent.", "اگر برای این ایمیل حسابی وجود داشته باشد، پیوند بازنشانی گذرواژه برای آن ارسال شده است."),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("Unable to request a password reset. Please try again.", "درخواست بازنشانی گذرواژه ثبت نشد. دوباره تلاش کنید."),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h1>{t("Forgot your password?", "گذرواژه‌تان را فراموش کرده‌اید؟")}</h1>
        <p>
          {t("Enter your email address and we'll send you a link to reset your password.", "نشانی ایمیل‌تان را وارد کنید تا پیوند بازنشانی گذرواژه را برایتان بفرستیم.")}
        </p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
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

        {message && (
          <div className={styles.success} role="status">
            {message}
          </div>
        )}

        {error && (
          <div className={styles.error} role="alert">
            {localizeAccountMessage(locale, error, "درخواست بازنشانی گذرواژه ثبت نشد. دوباره تلاش کنید.")}
          </div>
        )}

        <Button
          type="submit"
          className={styles.submit}
          loading={loading}
        >
          {t("Send reset link", "ارسال پیوند بازنشانی")}
        </Button>
      </form>

      <Link href="/login" className={styles.backLink}>
        <span aria-hidden="true">{t("←", "→")}</span>
        {t("Back to sign in", "بازگشت به ورود")}
      </Link>
    </AuthShell>
  );
}
