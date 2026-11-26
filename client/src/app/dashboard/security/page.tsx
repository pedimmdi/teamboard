"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import PasswordField from "@/components/auth/PasswordField";
import { changePassword } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import styles from "../dashboard.module.css";

function AlertIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="6.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M10 6.8V10.2M10 13.1V13.2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M4.5 10.5L8 14L15.5 6.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const commonPasswords = new Set([
  "password",
  "password123",
  "12345678",
  "123456789",
  "1234567890",
  "qwerty123",
  "qwertyuiop",
  "letmein",
  "welcome",
  "admin123",
]);

export default function SecurityPage() {
  const { locale, t } = useLocale();
  const router = useRouter();
  const { accessToken, isAuthenticated, isLoading, logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const requirements = useMemo(
    () => ({
      length: newPassword.length >= 8,
      notNumeric: newPassword.length > 0 && !/^\d+$/.test(newPassword),
      notCommon:
        newPassword.length > 0 &&
        !commonPasswords.has(newPassword.toLowerCase()),
    }),
    [newPassword],
  );

  if (isLoading || !isAuthenticated || !accessToken) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setErrorMessage("");

    if (!currentPassword || !newPassword || !passwordConfirm) {
      setErrorMessage(t("All password fields are required.", "همه فیلدهای گذرواژه را پر کنید."));
      return;
    }

    if (newPassword !== passwordConfirm) {
      setErrorMessage(t("New password and confirmation do not match.", "گذرواژه جدید با تکرار آن یکسان نیست."));
      return;
    }

    setIsSaving(true);

    try {
      await changePassword(accessToken, {
        current_password: currentPassword,
        new_password: newPassword,
        password_confirm: passwordConfirm,
      });

      await logout();
      router.replace("/login");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t("Unable to change your password.", "تغییر گذرواژه انجام نشد."),
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className={styles.page}>
      <div className={styles.content}>
        <header className={styles.pageHeader}>
          <div>
            <h1>{t("Security", "امنیت")}</h1>
            <p>{t("Update your password to keep your account secure.", "برای حفظ امنیت حسابتان، گذرواژه خود را به‌روز کنید.")}</p>
          </div>
        </header>

        <form className={styles.card} onSubmit={handleSubmit}>
          <div className={styles.warningAlert}>
            <span className={styles.alertIcon}>
              <AlertIcon />
            </span>
            <p>
              {t("You'll be signed out on all devices after changing your password.", "پس از تغییر گذرواژه، از حساب خود در همه دستگاه‌ها خارج می‌شوید.")}
            </p>
          </div>

          <div className={styles.passwordFields}>
            <PasswordField
              id="current-password"
              name="current_password"
              label={t("Current password", "گذرواژه فعلی")}
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              visibilityLabels={{
                show: t("Show current password", "نمایش گذرواژه فعلی"),
                hide: t("Hide current password", "پنهان کردن گذرواژه فعلی"),
              }}
            />
            <PasswordField
              id="new-password"
              name="new_password"
              label={t("New password", "گذرواژه جدید")}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              visibilityLabels={{
                show: t("Show new password", "نمایش گذرواژه جدید"),
                hide: t("Hide new password", "پنهان کردن گذرواژه جدید"),
              }}
            />
            <PasswordField
              id="confirm-new-password"
              name="password_confirm"
              label={t("Confirm new password", "تکرار گذرواژه جدید")}
              value={passwordConfirm}
              onChange={(event) => setPasswordConfirm(event.target.value)}
              autoComplete="new-password"
              visibilityLabels={{
                show: t("Show password confirmation", "نمایش تکرار گذرواژه"),
                hide: t("Hide password confirmation", "پنهان کردن تکرار گذرواژه"),
              }}
            />
          </div>

          <div className={styles.requirements}>
            <div
              className={`${styles.requirement} ${
                requirements.length ? styles.requirementMet : ""
              }`}
            >
              <span className={styles.requirementIcon}>
                <CheckIcon />
              </span>
              <span>{t("At least 8 characters", "حداقل ۸ نویسه")}</span>
            </div>

            <div
              className={`${styles.requirement} ${
                requirements.notNumeric ? styles.requirementMet : ""
              }`}
            >
              <span className={styles.requirementIcon}>
                <CheckIcon />
              </span>
              <span>{t("Not entirely numeric", "شامل چیزی بیش از اعداد")}</span>
            </div>

            <div
              className={`${styles.requirement} ${
                requirements.notCommon ? styles.requirementMet : ""
              }`}
            >
              <span className={styles.requirementIcon}>
                <CheckIcon />
              </span>
              <span>{t("Not a commonly used password", "گذرواژه‌ای غیرمتداول")}</span>
            </div>
          </div>

          {errorMessage && (
            <p className={styles.errorMessage}>{localizeAccountMessage(locale, errorMessage, "تغییر گذرواژه انجام نشد.")}</p>
          )}

          <div className={styles.actions}>
            <button
              type="submit"
              className={styles.primaryButton}
              disabled={isSaving}
            >
              {isSaving ? t("Updating...", "در حال به‌روزرسانی…") : t("Update password", "تغییر گذرواژه")}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}