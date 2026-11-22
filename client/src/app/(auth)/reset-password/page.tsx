
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { FormEvent, useState } from "react";
import Link from "next/link";

import AuthShell from "@/components/auth/AuthShell";
import PasswordField from "@/components/auth/PasswordField";
import Button from "@/components/ui/Button";
import { confirmPasswordReset } from "@/lib/api";

import styles from "./reset-password.module.css";

export default function ResetPasswordPage() {
  const { locale, t } = useLocale();
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const requirements = [
    {
      label: t("At least 8 characters", "حداقل ۸ نویسه"),
      met: password.length >= 8,
    },
    {
      label: t("Not entirely numeric", "شامل چیزی بیش از اعداد"),
      met: password.length > 0 && !/^\d+$/.test(password),
    },
    {
      label: t("Passwords match", "گذرواژه‌ها یکسان‌اند"),
      met: passwordConfirm.length > 0 && password === passwordConfirm,
    },
  ];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (password !== passwordConfirm) {
      setError(t("Passwords do not match.", "گذرواژه‌ها یکسان نیستند."));
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const uid = params.get("uid");
    const token = params.get("token");

    if (!uid || !token) {
      setError(t("This password reset link is invalid or incomplete.", "پیوند بازنشانی گذرواژه نامعتبر یا ناقص است."));
      return;
    }

    setLoading(true);

    try {
      const result = await confirmPasswordReset(
        uid,
        token,
        password,
        passwordConfirm,
      );

      setMessage(
        (locale === "en" && result.detail) || t("Your password has been reset successfully.", "گذرواژه‌تان بازنشانی شد."),
      );
      setPassword("");
      setPasswordConfirm("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("Unable to reset your password. Please try again.", "گذرواژه بازنشانی نشد. دوباره تلاش کنید."),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className={styles.header}>
        <h1>{t("Set a new password", "گذرواژه جدید تعیین کنید")}</h1>
        <p>
          {t("Create a strong password for your account. It should be different from your previous password.", "برای حسابتان گذرواژه‌ای قوی و متفاوت از گذرواژه قبلی انتخاب کنید.")}
        </p>
      </div>

      {message ? (
        <div className={styles.completed}>
          <p className={styles.success} role="status">
            {message}
          </p>
          <Link href="/login" className={styles.submitLink}>
            {t("Continue to sign in", "رفتن به صفحه ورود")}
          </Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit}>
          <PasswordField
            id="new-password"
            name="new-password"
            label={t("New password", "گذرواژه جدید")}
            placeholder={t("Enter a new password", "گذرواژه جدید را وارد کنید")}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <PasswordField
            id="confirm-password"
            name="confirm-password"
            label={t("Confirm new password", "تکرار گذرواژه جدید")}
            placeholder={t("Repeat your new password", "گذرواژه جدید را دوباره وارد کنید")}
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            required
          />

          <div className={styles.requirements}>
            {requirements.map((requirement) => (
              <div
                key={requirement.label}
                className={`${styles.requirement} ${
                  requirement.met ? styles.met : ""
                }`}
              >
                <span aria-hidden="true">
                  {requirement.met ? "✓" : "○"}
                </span>
                {requirement.label}
              </div>
            ))}
          </div>

          {error && (
            <div className={styles.error} role="alert">
              {localizeAccountMessage(locale, error, "گذرواژه بازنشانی نشد. دوباره تلاش کنید.")}
            </div>
          )}

          <Button
            type="submit"
            className={styles.submit}
            loading={loading}
          >
            {t("Reset password", "بازنشانی گذرواژه")}
          </Button>
        </form>
      )}

      {!message && (
        <Link href="/login" className={styles.backLink}>
          <span aria-hidden="true">{t("←", "→")}</span>
          {t("Back to sign in", "بازگشت به ورود")}
        </Link>
      )}
    </AuthShell>
  );
}
