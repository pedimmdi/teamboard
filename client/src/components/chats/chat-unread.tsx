"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getUnreadChats, markChatRead, type ChatUnreadSummary } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import styles from "./chats.module.css";

const empty: ChatUnreadSummary = {unread_count: 0, conversations: []};
const ChatUnread = createContext<{
  summary: ChatUnreadSummary; failed: boolean; refresh: () => void;
  markRead: (conversation: string, message: string) => Promise<void>;
}>({summary: empty, failed: false, refresh: () => {}, markRead: async () => {}});
export const useChatUnread = () => useContext(ChatUnread);

export function ChatUnreadProvider({slug, children}: {slug?: string; children: React.ReactNode}) {
  const {accessToken, user} = useAuth();
  const userId = user?.id;
  const [result, setResult] = useState<{key: string; summary: ChatUnreadSummary}>();
  const [failedKey, setFailedKey] = useState<string>();
  const [revision, setRevision] = useState(0);
  const key = JSON.stringify([userId, slug]);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!accessToken || !slug || userId === undefined) return;
    const controller = new AbortController();
    getUnreadChats(accessToken, slug, controller.signal).then((summary) => {
      if (!controller.signal.aborted) { setResult({key, summary}); setFailedKey(undefined); }
    }).catch(() => {if (!controller.signal.aborted) setFailedKey(key);});
    return () => controller.abort();
  }, [accessToken, slug, userId, key, revision]);
  useEffect(() => {
    const visible = () => {if (!document.hidden) refresh();};
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    const timer = window.setInterval(visible, 15_000);
    return () => {window.clearInterval(timer); window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible);};
  }, [refresh]);
  const markRead = useCallback(async (conversation: string, message: string) => {
    if (!accessToken || !slug) return;
    await markChatRead(accessToken, slug, conversation, message);
    refresh();
  }, [accessToken, slug, refresh]);
  return <ChatUnread.Provider value={{summary: result?.key === key ? result.summary : empty, failed: failedKey === key, refresh, markRead}}>{children}</ChatUnread.Provider>;
}

export function ChatUnreadBadge({count}: {count: number}) {
  const { ui, formatNumber } = useWorkspaceLocale();
  return count > 0 ? <span className={styles.unreadBadge} dir="ltr" aria-label={ui("{0} unread messages", count)}>{count > 10 ? "+" + formatNumber(10) : formatNumber(count)}</span> : null;
}
