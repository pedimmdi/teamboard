"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { useEffect, useState } from "react";

import {
  ApiError,
  getSessions,
  revokeOtherSessions,
  revokeSession,
  type PaginatedSessions,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { regionalLocale } from "@/lib/locale";

import styles from "../dashboard.module.css";

function MonitorIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect
        x="2.5"
        y="3"
        width="15"
        height="10"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M7 17H13M10 13V17"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect
        x="5.5"
        y="2.5"
        width="9"
        height="15"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M9 14.5H11"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

type Translator = ReturnType<typeof useLocale>["t"];

function getDeviceInfo(userAgent: string, t: Translator) {
  const ua = userAgent.toLowerCase();

  const isIPhone = ua.includes("iphone");
  const isIPad = ua.includes("ipad");
  const isAndroid = ua.includes("android");

  let browser = t("Browser", "مرورگر");

  if (ua.includes("edg/")) {
    browser = t("Edge", "اج");
  } else if (ua.includes("chrome") && !ua.includes("edg/")) {
    browser = t("Chrome", "کروم");
  } else if (ua.includes("firefox")) {
    browser = t("Firefox", "فایرفاکس");
  } else if (ua.includes("safari") && !ua.includes("chrome")) {
    browser = t("Safari", "سافاری");
  }

  const deviceLabel = (english: string, persian: string) => t(
    `${browser} on ${english}`,
    `${browser} در ${persian}`,
  );

  if (isIPhone) {
    return {
      name: deviceLabel("iPhone", "آیفون"),
      type: "phone" as const,
    };
  }

  if (isIPad) {
    return {
      name: deviceLabel("iPad", "آیپد"),
      type: "phone" as const,
    };
  }

  if (isAndroid) {
    return {
      name: deviceLabel("Android", "اندروید"),
      type: "phone" as const,
    };
  }

  let name = deviceLabel("Desktop", "رایانه");

  if (ua.includes("mac os")) {
    name = deviceLabel("macOS", "مک");
  } else if (ua.includes("windows")) {
    name = deviceLabel("Windows", "ویندوز");
  } else if (ua.includes("linux")) {
    name = deviceLabel("Linux", "لینوکس");
  }

  return {
    name,
    type: "desktop" as const,
  };
}

function formatRelativeTime(dateString: string, locale: ReturnType<typeof useLocale>["locale"], t: Translator) {
  const timestamp = new Date(dateString).getTime();

  if (Number.isNaN(timestamp)) {
    return t("Unknown", "نامشخص");
  }

  const diff = Math.max(0, Date.now() - timestamp);
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) {
    return t("just now", "همین حالا");
  }

  const formatter = new Intl.RelativeTimeFormat(regionalLocale(locale));
  if (minutes < 60) {
    return formatter.format(-minutes, "minute");
  }

  const hours = Math.floor(minutes / 60);

  if (hours < 24) {
    return formatter.format(-hours, "hour");
  }

  const days = Math.floor(hours / 24);

  return formatter.format(-days, "day");
}

export default function SessionsPage() {
  const { locale, t, formatNumber } = useLocale();
  const { accessToken, isAuthenticated, isLoading } = useAuth();

  const [loadedPage, setLoadedPage] = useState<{ number: number; data: PaginatedSessions } | null>(null);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [isRevokingOthers, setIsRevokingOthers] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (isLoading || !isAuthenticated || !accessToken) {
      return;
    }

    let cancelled = false;

    const fetchSessions = async () => {
      setIsLoadingSessions(true);
      setErrorMessage("");

      try {
        const data = await getSessions(accessToken, page);

        if (!cancelled) {
          setLoadedPage({ number: page, data });
        }
      } catch (error) {
        if (!cancelled) {
          if (page > 1 && error instanceof ApiError && error.status === 404) {
            setPage(1);
            return;
          }
          setErrorMessage(
            error instanceof Error
              ? error.message
              : t("Unable to load active sessions.", "نشست‌های فعال بارگیری نشدند."),
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSessions(false);
        }
      }
    };

    void fetchSessions();

    return () => {
      cancelled = true;
    };
  }, [accessToken, isAuthenticated, isLoading, page, revision, t]);

  if (isLoading || !isAuthenticated || !accessToken) {
    return null;
  }

  const sessionPage = loadedPage?.data;
  const displayedPage = loadedPage?.number ?? 1;

  const loadPage = (nextPage: number) => {
    setPage(nextPage);
    setRevision((current) => current + 1);
  };

  const handleRevoke = async (sessionId: string) => {
    setRevokingId(sessionId);
    setErrorMessage("");

    try {
      await revokeSession(accessToken, sessionId);
      const emptiedPage = sessionPage?.results.length === 1 && displayedPage > 1;
      loadPage(emptiedPage ? displayedPage - 1 : displayedPage);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t("Unable to revoke this session.", "پایان دادن به این نشست انجام نشد."),
      );
    } finally {
      setRevokingId(null);
    }
  };

  const handleRevokeOthers = async () => {
    setIsRevokingOthers(true);
    setErrorMessage("");

    try {
      await revokeOtherSessions(accessToken);
      loadPage(1);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t("Unable to sign out of other devices.", "خروج از حساب در سایر دستگاه‌ها انجام نشد."),
      );
    } finally {
      setIsRevokingOthers(false);
    }
  };

  const sessions = sessionPage?.results ?? [];
  const hasOtherSessions = (sessionPage?.count ?? 0) > 1 || sessions.some((session) => !session.is_current);
  const busy = isLoadingSessions || isRevokingOthers || revokingId !== null;

  return (
    <section className={styles.page}>
      <div className={styles.content}>
        <header className={styles.pageHeaderWithAction}>
          <div>
            <h1>{t("Active sessions", "نشست‌های فعال")}</h1>
            <p>{t("Devices that are currently signed in to your account.", "دستگاه‌هایی که اکنون به حساب شما وارد شده‌اند.")}</p>
          </div>

          <button
            type="button"
            className={styles.dangerButton}
            onClick={handleRevokeOthers}
            disabled={busy || !hasOtherSessions}
          >
            {isRevokingOthers
              ? t("Signing out...", "در حال خروج…")
              : t("Sign out of other devices", "خروج از حساب در سایر دستگاه‌ها")}
          </button>
        </header>

        {errorMessage && (
          <div>
            <p role="alert" className={styles.errorMessage}>
              {localizeAccountMessage(locale, errorMessage, "عملیات نشست انجام نشد. دوباره تلاش کنید.")}
            </p>
            <button type="button" className={styles.secondaryButton} disabled={busy} onClick={() => loadPage(page)}>
              {t("Reload sessions", "بارگیری دوبارهٔ نشست‌ها")}
            </button>
          </div>
        )}

        <div className={styles.sessionsList}>
          {isLoadingSessions ? (
            <div className={styles.emptyState}>{t("Loading sessions...", "در حال بارگیری نشست‌ها…")}</div>
          ) : sessions.length === 0 ? (
            <div className={styles.emptyState}>{t("No active sessions found.", "نشست فعالی پیدا نشد.")}</div>
          ) : (
            sessions.map((session) => {
              const device = getDeviceInfo(session.user_agent, t);

              return (
                <div
                  key={session.id}
                  className={styles.sessionCard}
                >
                  <div className={styles.deviceIcon}>
                    {device.type === "phone" ? (
                      <PhoneIcon />
                    ) : (
                      <MonitorIcon />
                    )}
                  </div>

                  <div className={styles.sessionDetails}>
                    <div className={styles.sessionTitleRow}>
                      <span className={styles.sessionTitle}>
                        {device.name}
                      </span>

                      {session.is_current && (
                        <span className={styles.successBadge}>
                          {t("This device", "این دستگاه")}
                        </span>
                      )}
                    </div>

                    <p>
                      {t("IP", "نشانی IP")} <bdi>{session.ip_address ?? t("Unavailable", "در دسترس نیست")}</bdi>
                      {" · "}{t("Last active", "آخرین فعالیت")}{" "}
                      {formatRelativeTime(session.last_seen_at, locale, t)}
                    </p>
                  </div>

                  {!session.is_current && (
                    <button
                      type="button"
                      className={styles.dangerButton}
                      onClick={() => handleRevoke(session.id)}
                      disabled={busy}
                    >
                      {revokingId === session.id ? t("Revoking...", "در حال پایان دادن…") : t("Revoke", "پایان دادن به نشست")}
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        {(sessionPage?.previous || sessionPage?.next) && (
          <nav className={styles.sessionsPagination} aria-label={t("Session pages", "صفحه‌های نشست‌ها")}>
            <button type="button" className={styles.secondaryButton}
              disabled={busy || !sessionPage.previous} onClick={() => loadPage(displayedPage - 1)}>
              {t("Previous page", "صفحهٔ قبل")}
            </button>
            <span aria-live="polite">{t(`Page ${formatNumber(displayedPage)}`, `صفحهٔ ${formatNumber(displayedPage)}`)}</span>
            <button type="button" className={styles.secondaryButton}
              disabled={busy || !sessionPage.next} onClick={() => loadPage(displayedPage + 1)}>
              {t("Next page", "صفحهٔ بعد")}
            </button>
          </nav>
        )}

        <p className={styles.sessionHint}>
          {t("Revoking a session signs that device out immediately.", "پایان دادن به نشست بلافاصله آن دستگاه را از حسابتان خارج می‌کند.")}
        </p>
      </div>
    </section>
  );
}
