"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getUnreadNotificationCount } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const NotificationCount = createContext<{
  count: number | null;
  refresh: () => void;
}>({ count: null, refresh: () => {} });

export function useNotificationCount() {
  return useContext(NotificationCount);
}

export function NotificationCountProvider({ children }: { children: React.ReactNode }) {
  const { accessToken, user } = useAuth();
  const userId = user?.id;
  const [result, setResult] = useState<{ userId: number; count: number }>();
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    if (!accessToken || userId === undefined) return;
    const controller = new AbortController();
    getUnreadNotificationCount(accessToken, controller.signal)
      .then(({ unread_count }) => {
        if (!controller.signal.aborted) setResult({ userId, count: unread_count });
      })
      .catch(() => {});
    return () => controller.abort();
  }, [accessToken, userId, revision]);

  useEffect(() => {
    window.addEventListener("focus", refresh);
    const interval = window.setInterval(() => {
      if (!document.hidden) refresh();
    }, 60_000);
    return () => {
      window.removeEventListener("focus", refresh);
      window.clearInterval(interval);
    };
  }, [refresh]);

  return (
    <NotificationCount.Provider value={{
      count: result && result.userId === userId ? result.count : null,
      refresh,
    }}>
      {children}
    </NotificationCount.Provider>
  );
}

export function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
    </svg>
  );
}
