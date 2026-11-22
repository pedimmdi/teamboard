"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  acceptNotificationInvitation,
  NOTIFICATION_PAGE_SIZE,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationFilter,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BellIcon, useNotificationCount } from "./notification-count";
import { notificationContent } from "./notification-content";
import styles from "./notifications.module.css";
import dashboardStyles from "../dashboard.module.css";

type InboxPage = Awaited<ReturnType<typeof getNotifications>>;

export default function NotificationsPage() {
  const { locale, t, formatDate, formatNumber } = useLocale();
  const filters = { all: t("All", "همه"), unread: t("Unread", "خوانده‌نشده"), read: t("Read", "خوانده‌شده") };
  const emptyTitle = {
    all: t("You are all caught up", "اعلان تازه‌ای ندارید"),
    unread: t("No unread notifications", "اعلان خوانده‌نشده‌ای ندارید"),
    read: t("No read notifications", "اعلان خوانده‌شده‌ای ندارید"),
  };
  const { accessToken } = useAuth();
  const { count, failed, refresh } = useNotificationCount();
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; data: InboxPage | null }>();
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState("");
  const queryKey = `${filter}:${page}:${revision}`;
  const response = result?.key === queryKey ? result : undefined;
  const data = response?.data;
  const loading = !response;

  useEffect(() => {
    if (!accessToken) return;
    const controller = new AbortController();
    getNotifications(accessToken, filter, page, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key: queryKey, data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        // A mutation or access change can remove the last page.
        if (page > 1 && error instanceof ApiError && error.status === 404) {
          setPage((current) => current - 1);
        } else {
          setResult({ key: queryKey, data: null });
        }
      });
    return () => controller.abort();
  }, [accessToken, filter, page, queryKey]);

  function reload() {
    setRevision((value) => value + 1);
    refresh();
  }

  async function markRead(id?: string, acceptInvitation = false) {
    if (!accessToken || pending) return;
    setPending(true);
    setActionError("");
    try {
      if (id && acceptInvitation) await acceptNotificationInvitation(accessToken, id);
      else if (id) await markNotificationRead(accessToken, id);
      else await markAllNotificationsRead(accessToken);
      reload();
    } catch (error) {
      setActionError(acceptInvitation
        ? (error instanceof ApiError ? error.message : t("Unable to accept the invitation.", "دعوت پذیرفته نشد."))
        : t("Unable to mark notifications as read. Please try again.", "اعلان‌ها به‌عنوان خوانده‌شده علامت نخوردند. دوباره تلاش کنید."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={dashboardStyles.page}>
      <section className={styles.inbox} aria-labelledby="inbox-title">
        <header className={styles.heading}>
          <span className={styles.headingIcon}><BellIcon /></span>
          <div>
            <h1 id="inbox-title">{t("Notifications", "اعلان‌ها")}</h1>
            <p>{t("Activity across your workspaces, projects and tasks.", "فعالیت‌های فضاهای کاری، پروژه‌ها و وظایف شما.")}</p>
          </div>
        </header>

        <div className={styles.panel}>
          <div className={styles.toolbar}>
            <div className={styles.filters} role="group" aria-label={t("Filter notifications", "فیلتر اعلان‌ها")}>
              {(Object.keys(filters) as NotificationFilter[]).map((value) => (
                <button key={value} type="button" aria-pressed={filter === value}
                  onClick={() => {
                    if (value === filter) return;
                    setFilter(value);
                    setPage(1);
                    setActionError("");
                  }}>
                  {filters[value]}
                </button>
              ))}
            </div>
            <div className={styles.actions}>
              {failed && <button type="button" onClick={refresh}>{t("Retry unread count", "تلاش دوباره برای دریافت تعداد اعلان‌ها")}</button>}
              {count !== null && <span aria-live="polite">{t(`${formatNumber(count)} unread`, `${formatNumber(count)} خوانده‌نشده`)}</span>}
              <button type="button" disabled={pending || loading || (!failed && count === 0)}
                onClick={() => void markRead()}>
                {t("Mark all as read", "علامت‌گذاری همه به‌عنوان خوانده‌شده")}
              </button>
            </div>
          </div>

          {actionError && <p className={styles.actionError} role="alert">{localizeAccountMessage(locale, actionError, "تغییر اعلان انجام نشد. دوباره تلاش کنید.")}</p>}

          {loading ? (
            <p className={styles.state} role="status">{t("Loading notifications…", "در حال بارگیری اعلان‌ها…")}</p>
          ) : !data ? (
            <div className={styles.state}>
              <h2>{t("Unable to load notifications", "اعلان‌ها بارگیری نشدند")}</h2>
              <p>{t("Check your connection and try again.", "اتصال خود را بررسی کنید و دوباره تلاش کنید.")}</p>
              <button className={styles.primary} type="button" onClick={reload}>{t("Try again", "تلاش دوباره")}</button>
            </div>
          ) : data.results.length === 0 ? (
            <div className={styles.state}>
              <span className={styles.headingIcon}><BellIcon /></span>
              <h2>{emptyTitle[filter]}</h2>
              <p>{filter === "all" ? t("New activity will appear here.", "فعالیت‌های جدید اینجا نمایش داده می‌شوند.") : t("Try another filter to see more activity.", "برای دیدن فعالیت‌های بیشتر، فیلتر دیگری را انتخاب کنید.")}</p>
            </div>
          ) : (
            <>
              <ul className={styles.list}>
                {data.results.map((notification) => {
                  const { title, icon, tone, href, description } = notificationContent(notification, locale);
                  return (
                    <li key={notification.id} className={styles.row} data-unread={!notification.is_read}>
                      <span className={styles.icon} data-tone={tone} aria-hidden="true">{icon}</span>
                      <div className={styles.content}>
                        {href ? <Link href={href}>{title}</Link> : <strong>{title}</strong>}
                        {description && <p dir="auto">{description}</p>}
                      </div>
                      <div className={styles.rowActions}>
                        <time dateTime={notification.created_at}>
                          {formatDate(notification.created_at, { dateStyle: "medium", timeStyle: "short" })}
                        </time>
                        {notification.event_type === "workspace_invited" && (
                        <button type="button" disabled={pending}
                          onClick={() => void markRead(notification.id, true)}>
                          {t("Accept invitation", "پذیرش دعوت")}
                        </button>
                      )}
                      {!notification.is_read && (
                          <button type="button" disabled={pending}
                            aria-label={t(`Mark as read: ${title}`, `علامت‌گذاری «${title}» به‌عنوان خوانده‌شده`)}
                            onClick={() => void markRead(notification.id)}>
                            {t("Mark as read", "علامت‌گذاری به‌عنوان خوانده‌شده")}
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <footer className={styles.footer}>
                <span>{t("Showing", "نمایش")} <bdi>{formatNumber((page - 1) * NOTIFICATION_PAGE_SIZE + 1)}–{formatNumber((page - 1) * NOTIFICATION_PAGE_SIZE + data.results.length)}</bdi> {t("of", "از")} {formatNumber(data.count)}</span>
                <div>
                  <button type="button" disabled={!data.previous} onClick={() => setPage(page - 1)}>{t("Previous", "قبلی")}</button>
                  <button type="button" disabled={!data.next} onClick={() => setPage(page + 1)}>{t("Next", "بعدی")}</button>
                </div>
              </footer>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
