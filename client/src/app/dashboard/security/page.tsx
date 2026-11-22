"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { changePassword } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import styles from "../dashboard.module.css";

function EyeIcon({ visible }: { visible: boolean }) {
  if (visible) {
    return (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path
          d="M2.5 10C4.3 6.8 6.8 5 10 5C13.2 5 15.7 6.8 17.5 10C15.7 13.2 13.2 15 10 15C6.8 15 4.3 13.2 2.5 10Z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <circle cx="10" cy="10" r="2.25" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M3 3L17 17"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M4 7.1C3.4 7.9 2.9 8.9 2.5 10C4.3 13.2 6.8 15 10 15C11.1 15 12.1 14.8 13 14.3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M7.1 4.8C8 4.3 8.9 4 10 4C13.2 4 15.7 5.8 17.5 9C17.1 9.8 16.7 10.5 16.2 11.1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

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

  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);

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
            <label className={styles.field}>
              <span>{t("Current password", "گذرواژه فعلی")}</span>

              <div className={styles.passwordInput}>
                <input
                  type={showCurrentPassword ? "text" : "password"}
                  value={currentPassword}
                  onChange={(event) =>
                    setCurrentPassword(event.target.value)
                  }
                  autoComplete="current-password"
                />

                <button
                  type="button"
                  className={styles.visibilityButton}
                  onClick={() =>
                    setShowCurrentPassword((current) => !current)
                  }
                  aria-label={
                    showCurrentPassword
                      ? t("Hide current password", "پنهان کردن گذرواژه فعلی")
                      : t("Show current password", "نمایش گذرواژه فعلی")
                  }
                >
                  <EyeIcon visible={showCurrentPassword} />
                </button>
              </div>
            </label>

            <label className={styles.field}>
              <span>{t("New password", "گذرواژه جدید")}</span>

              <div className={styles.passwordInput}>
                <input
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                />

                <button
                  type="button"
                  className={styles.visibilityButton}
                  onClick={() => setShowNewPassword((current) => !current)}
                  aria-label={
                    showNewPassword
                      ? t("Hide new password", "پنهان کردن گذرواژه جدید")
                      : t("Show new password", "نمایش گذرواژه جدید")
                  }
                >
                  <EyeIcon visible={showNewPassword} />
                </button>
              </div>
            </label>

            <label className={styles.field}>
              <span>{t("Confirm new password", "تکرار گذرواژه جدید")}</span>

              <div className={styles.passwordInput}>
                <input
                  type={showPasswordConfirm ? "text" : "password"}
                  value={passwordConfirm}
                  onChange={(event) =>
                    setPasswordConfirm(event.target.value)
                  }
                  autoComplete="new-password"
                />

                <button
                  type="button"
                  className={styles.visibilityButton}
                  onClick={() =>
                    setShowPasswordConfirm((current) => !current)
                  }
                  aria-label={
                    showPasswordConfirm
                      ? t("Hide password confirmation", "پنهان کردن تکرار گذرواژه")
                      : t("Show password confirmation", "نمایش تکرار گذرواژه")
                  }
                >
                  <EyeIcon visible={showPasswordConfirm} />
                </button>
              </div>
            </label>
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