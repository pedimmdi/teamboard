"use client";

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

const filters = { all: "All", unread: "Unread", read: "Read" } as const;
const emptyTitle = {
  all: "You are all caught up",
  unread: "No unread notifications",
  read: "No read notifications",
};
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
type InboxPage = Awaited<ReturnType<typeof getNotifications>>;

export default function NotificationsPage() {
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
        ? (error instanceof ApiError ? error.message : "Unable to accept the invitation.")
        : "Unable to mark notifications as read. Please try again.");
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
            <h1 id="inbox-title">Notifications</h1>
            <p>Activity across your workspaces, projects and tasks.</p>
          </div>
        </header>

        <div className={styles.panel}>
          <div className={styles.toolbar}>
            <div className={styles.filters} role="group" aria-label="Filter notifications">
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
              {failed && <button type="button" onClick={refresh}>Retry unread count</button>}
              {count !== null && <span aria-live="polite">{count} unread</span>}
              <button type="button" disabled={pending || loading || (!failed && count === 0)}
                onClick={() => void markRead()}>
                Mark all as read
              </button>
            </div>
          </div>

          {actionError && <p className={styles.actionError} role="alert">{actionError}</p>}

          {loading ? (
            <p className={styles.state} role="status">Loading notifications…</p>
          ) : !data ? (
            <div className={styles.state}>
              <h2>Unable to load notifications</h2>
              <p>Check your connection and try again.</p>
              <button className={styles.primary} type="button" onClick={reload}>Try again</button>
            </div>
          ) : data.results.length === 0 ? (
            <div className={styles.state}>
              <span className={styles.headingIcon}><BellIcon /></span>
              <h2>{emptyTitle[filter]}</h2>
              <p>{filter === "all" ? "New activity will appear here." : "Try another filter to see more activity."}</p>
            </div>
          ) : (
            <>
              <ul className={styles.list}>
                {data.results.map((notification) => {
                  const { title, icon, tone, href, description } = notificationContent(notification);
                  return (
                    <li key={notification.id} className={styles.row} data-unread={!notification.is_read}>
                      <span className={styles.icon} data-tone={tone} aria-hidden="true">{icon}</span>
                      <div className={styles.content}>
                        {href ? <Link href={href}>{title}</Link> : <strong>{title}</strong>}
                        {description && <p>{description}</p>}
                      </div>
                      <div className={styles.rowActions}>
                        <time dateTime={notification.created_at}>
                          {dateFormat.format(new Date(notification.created_at))}
                        </time>
                        {notification.event_type === "workspace_invited" && (
                        <button type="button" disabled={pending}
                          onClick={() => void markRead(notification.id, true)}>
                          Accept invitation
                        </button>
                      )}
                      {!notification.is_read && (
                          <button type="button" disabled={pending}
                            aria-label={`Mark as read: ${title}`}
                            onClick={() => void markRead(notification.id)}>
                            Mark as read
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <footer className={styles.footer}>
                <span>Showing {(page - 1) * NOTIFICATION_PAGE_SIZE + 1}–{(page - 1) * NOTIFICATION_PAGE_SIZE + data.results.length} of {data.count}</span>
                <div>
                  <button type="button" disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
                  <button type="button" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </footer>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
