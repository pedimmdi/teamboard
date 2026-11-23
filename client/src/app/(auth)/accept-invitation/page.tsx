
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  acceptWorkspaceInvitation,
  ApiError,
  type AcceptWorkspaceInvitationResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PreferencesControls } from "@/components/preferences-controls";
import BrandMark from "@/components/ui/BrandMark";
import { clearInvitationReturn, saveInvitationReturn } from "@/lib/invitation-return";

import styles from "./accept-invitation.module.css";

type InvitationStatus = "ready" | "success" | "error";

function Brand() {
  const { locale, t } = useLocale();
  return (
    <header className={styles.header}>
      <Link href={locale === "fa" ? "/fa" : "/"} className={styles.brand}>
        <span className={styles.brandMark}><BrandMark /></span>
        <span>{t("TeamBoard", "تیم‌برد")}</span>
      </Link>
      <PreferencesControls compact />
    </header>
  );
}

function StatusIcon({
  status,
}: {
  status: "ready" | "success" | "error";
}) {
  return (
    <div className={`${styles.iconCircle} ${styles[status]}`}>
      {status === "ready" ? (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="4" y="6" width="16" height="12" rx="2" />
          <path d="m5 8 7 5 7-5" />
        </svg>
      ) : status === "success" ? (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="m8.5 12 2.5 2.5 4.5-5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v5M12 16h.01" />
        </svg>
      )}
    </div>
  );
}

function InvitationContent() {
  const { locale, t } = useLocale();
  const searchParams = useSearchParams();
  const invitationToken = searchParams.get("token")?.trim() ?? "";

  const {
    accessToken,
    isAuthenticated,
    isLoading,
    user,
    logout,
  } = useAuth();

  const router = useRouter();
  const [isSwitchingAccount, setIsSwitchingAccount] = useState(false);

  const [result, setResult] =
    useState<AcceptWorkspaceInvitationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const status: InvitationStatus = result
    ? "success"
    : !invitationToken || error
      ? "error"
      : "ready";

  const returnPath = `/accept-invitation/?${new URLSearchParams({
    token: invitationToken,
  }).toString()}`;

  const loginPath = `/login?${new URLSearchParams({
    next: returnPath,
  }).toString()}`;

  const registerPath = `/register?${new URLSearchParams({
    next: returnPath,
  }).toString()}`;

  async function handleSwitchAccount() {
    if (isSwitchingAccount) return;

    setIsSwitchingAccount(true);
    setAccountError(null);

    saveInvitationReturn(returnPath);

    try {
      await logout();
      router.replace(loginPath);
    } catch {
      setAccountError(t("Unable to sign out. Please try again.", "خروج از حساب انجام نشد. دوباره تلاش کنید."));
      setIsSwitchingAccount(false);
    }
  }

  async function handleAccept() {
    if (!accessToken || !invitationToken || isSubmitting || result) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await acceptWorkspaceInvitation(
        accessToken,
        invitationToken,
      );

      setResult(response);
      clearInvitationReturn();

      window.history.replaceState(
        window.history.state,
        "",
        "/accept-invitation/",
      );
    } catch (err) {
      if (err instanceof ApiError) {
        const tokenErrors = err.errors?.token;
        const emailErrors = err.errors?.email;
        const detailErrors = err.errors?.detail;

        const message = tokenErrors ?? emailErrors ?? detailErrors;

        setError(
          Array.isArray(message)
            ? message.join(" ")
            : typeof message === "string"
              ? message
              : err.message,
        );
      } else {
        setError(t("Unable to accept this invitation. Please try again.", "دعوت پذیرفته نشد. دوباره تلاش کنید."));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Brand />

        <section className={styles.card} aria-live="polite">
          <StatusIcon status={status} />

          {status === "success" && result ? (
            <>
              <h1>{t("You joined ", "به ")}<bdi>{result.workspace.name}</bdi>{t(".", " پیوستید.")}</h1>
              <p className={styles.description}>
                {t("You are now a member of this workspace. You can start collaborating with your team.", "اکنون عضو این فضای کاری هستید و می‌توانید همکاری با تیم را شروع کنید.")}
              </p>

              <Link
                className={styles.primaryButton}
                href={`/dashboard/workspaces/${encodeURIComponent(
                  result.workspace.slug,
                )}`}
              >
                {t("Go to Workspace", "رفتن به فضای کاری")}
              </Link>

              <Link
                className={styles.secondaryLink}
                href="/dashboard/workspaces"
              >
                {t("View all workspaces", "مشاهده همه فضاهای کاری")}
              </Link>
            </>
          ) : status === "error" ? (
            <>
              <h1>{t("This invitation can't be used", "امکان استفاده از این دعوت وجود ندارد")}</h1>
              <p className={styles.description}>
                {t("This invitation may be invalid, expired, revoked, or intended for another account.", "شاید دعوت نامعتبر، منقضی یا لغو شده باشد، یا برای حساب دیگری صادر شده باشد.")}
              </p>

              <div className={styles.errorMessage} role="alert">
                {error ? localizeAccountMessage(locale, error, "دعوت پذیرفته نشد. دوباره تلاش کنید.") : t("The invitation link is missing or invalid.", "پیوند دعوت ناقص یا نامعتبر است.")}
              </div>

              {isAuthenticated ? (
                <Link className={styles.primaryButton} href="/dashboard/workspaces">
                  {t("Go to workspaces", "رفتن به فضاهای کاری")}
                </Link>
              ) : (
                <Link className={styles.primaryButton} href={loginPath}>
                  {t("Sign in with another account", "ورود با حساب دیگر")}
                </Link>
              )}

              <Link
                className={styles.secondaryLink}
                href="/dashboard/workspaces"
              >
                {t("Go to workspaces", "رفتن به فضاهای کاری")}
              </Link>

              <p className={styles.helpText}>
                {t("If the invitation has expired or was revoked, ask an workspace admin to send a new one.", "اگر دعوت منقضی یا لغو شده، از مدیر فضای کاری بخواهید دعوت تازه‌ای بفرستد.")}
              </p>
            </>
          ) : (
            <>
              <h1>{t("Accept your invitation", "دعوت‌تان را بپذیرید")}</h1>

              <p className={styles.description}>
                {t("You've been invited to join an workspace on TeamBoard. Accept the invitation to collaborate with your team.", "برای پیوستن به یک فضای کاری در تیم‌بورد دعوت شده‌اید. دعوت را بپذیرید تا با تیمتان همکاری کنید.")}
              </p>

              {isLoading ? (
                <button className={styles.primaryButton} disabled>
                  {t("Checking session...", "در حال بررسی نشست…")}
                </button>
              ) : isAuthenticated ? (
                <>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    disabled={isSubmitting}
                    onClick={() => void handleAccept()}
                  >
                    {isSubmitting
                      ? t("Accepting invitation...", "در حال پذیرش دعوت…")
                      : t("Accept invitation", "پذیرش دعوت")}
                  </button>

                  {user && (
                    <p className={styles.accountHint}>
                      {t("Signed in as", "حساب فعلی")} {user.email}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <Link
                    className={styles.primaryButton}
                    href={loginPath}
                    onClick={() => saveInvitationReturn(returnPath)}
                  >
                    {t("Sign in to accept", "برای پذیرش وارد شوید")}
                  </Link>

                  <Link
                    className={styles.secondaryLink}
                    href={registerPath}
                    onClick={() => saveInvitationReturn(returnPath)}
                  >
                    {t("Don't have an account? Sign up", "حساب ندارید؟ ثبت‌نام کنید")}
                  </Link>
                </>
              )}

              {!isLoading && isAuthenticated && (
                <>
                  {accountError && (
                    <div className={styles.errorMessage} role="alert">
                      {accountError}
                    </div>
                  )}

                  <button
                    type="button"
                    className={styles.textButton}
                    disabled={isSwitchingAccount || isSubmitting}
                    onClick={() => void handleSwitchAccount()}
                  >
                    {isSwitchingAccount
                      ? t("Switching account...", "در حال تغییر حساب…")
                      : t("Not you? Use another account", "حساب دیگری دارید؟ با آن وارد شوید")}
                  </button>
                </>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default function AcceptInvitationPage() {
  const { t } = useLocale();
  return (
    <Suspense
      fallback={
        <main className={styles.page}>
          <div className={styles.container}>
            <Brand />
            <div className={styles.card}>
              <p className={styles.description}>{t("Loading invitation...", "در حال بارگیری دعوت…")}</p>
            </div>
          </div>
        </main>
      }
    >
      <InvitationContent />
    </Suspense>
  );
}
