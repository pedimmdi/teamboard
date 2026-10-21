"use client";

import { useEffect, useState } from "react";

import {
  getSessions,
  revokeOtherSessions,
  revokeSession,
  UserSession,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

function getDeviceInfo(userAgent: string) {
  const ua = userAgent.toLowerCase();

  const isIPhone = ua.includes("iphone");
  const isIPad = ua.includes("ipad");
  const isAndroid = ua.includes("android");

  let browser = "Browser";

  if (ua.includes("edg/")) {
    browser = "Edge";
  } else if (ua.includes("chrome") && !ua.includes("edg/")) {
    browser = "Chrome";
  } else if (ua.includes("firefox")) {
    browser = "Firefox";
  } else if (ua.includes("safari") && !ua.includes("chrome")) {
    browser = "Safari";
  }

  if (isIPhone) {
    return {
      name: `${browser} on iPhone`,
      type: "phone" as const,
    };
  }

  if (isIPad) {
    return {
      name: `${browser} on iPad`,
      type: "phone" as const,
    };
  }

  if (isAndroid) {
    return {
      name: `${browser} on Android`,
      type: "phone" as const,
    };
  }

  let operatingSystem = "Desktop";

  if (ua.includes("mac os")) {
    operatingSystem = "macOS";
  } else if (ua.includes("windows")) {
    operatingSystem = "Windows";
  } else if (ua.includes("linux")) {
    operatingSystem = "Linux";
  }

  return {
    name: `${browser} on ${operatingSystem}`,
    type: "desktop" as const,
  };
}

function formatRelativeTime(dateString: string) {
  const timestamp = new Date(dateString).getTime();

  if (Number.isNaN(timestamp)) {
    return "Unknown";
  }

  const diff = Math.max(0, Date.now() - timestamp);
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) {
    return "just now";
  }

  if (minutes < 60) {
    return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  }

  const hours = Math.floor(minutes / 60);

  if (hours < 24) {
    return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  }

  const days = Math.floor(hours / 24);

  return `${days} ${days === 1 ? "day" : "days"} ago`;
}

export default function SessionsPage() {
  const { accessToken, isAuthenticated, isLoading } = useAuth();

  const [sessions, setSessions] = useState<UserSession[]>([]);
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
        const data = await getSessions(accessToken);

        if (!cancelled) {
          setSessions(data);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Unable to load active sessions.",
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
  }, [accessToken, isAuthenticated, isLoading]);

  if (isLoading || !isAuthenticated || !accessToken) {
    return null;
  }

  const handleRevoke = async (sessionId: string) => {
    setRevokingId(sessionId);
    setErrorMessage("");

    try {
      await revokeSession(accessToken, sessionId);
      setSessions((current) =>
        current.filter((session) => session.id !== sessionId),
      );
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to revoke this session.",
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

      const data = await getSessions(accessToken);
      setSessions(data);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to sign out of other devices.",
      );
    } finally {
      setIsRevokingOthers(false);
    }
  };

  const otherSessions = sessions.filter((session) => !session.is_current);

  return (
    <section className={styles.page}>
      <div className={styles.content}>
        <header className={styles.pageHeaderWithAction}>
          <div>
            <h1>Active sessions</h1>
            <p>Devices that are currently signed in to your account.</p>
          </div>

          <button
            type="button"
            className={styles.dangerButton}
            onClick={handleRevokeOthers}
            disabled={isRevokingOthers || otherSessions.length === 0}
          >
            {isRevokingOthers
              ? "Signing out..."
              : "Sign out of other devices"}
          </button>
        </header>

        {errorMessage && (
          <p className={styles.errorMessage}>{errorMessage}</p>
        )}

        <div className={styles.sessionsList}>
          {isLoadingSessions ? (
            <div className={styles.emptyState}>Loading sessions...</div>
          ) : sessions.length === 0 ? (
            <div className={styles.emptyState}>No active sessions found.</div>
          ) : (
            sessions.map((session) => {
              const device = getDeviceInfo(session.user_agent);

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
                          This device
                        </span>
                      )}
                    </div>

                    <p>
                      IP {session.ip_address ?? "Unavailable"} · Last active{" "}
                      {formatRelativeTime(session.last_seen_at)}
                    </p>
                  </div>

                  {!session.is_current && (
                    <button
                      type="button"
                      className={styles.dangerButton}
                      onClick={() => handleRevoke(session.id)}
                      disabled={revokingId === session.id}
                    >
                      {revokingId === session.id ? "Revoking..." : "Revoke"}
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        <p className={styles.sessionHint}>
          Revoking a session signs that device out immediately.
        </p>
      </div>
    </section>
  );
}