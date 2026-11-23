"use client";

import { useSyncExternalStore } from "react";
import { useLocale } from "@/lib/preferences";
import { IRAN_TIME_ZONE } from "@/lib/iran-time";
import styles from "./calendar.module.css";

const minute = () => Math.floor(Date.now() / 60_000) * 60_000;
const serverSnapshot = () => null;

function subscribe(onChange: () => void) {
  const delay = 60_000 - Date.now() % 60_000;
  let interval: ReturnType<typeof setInterval> | undefined;
  const first = setTimeout(() => {
    onChange();
    interval = setInterval(onChange, 60_000);
  }, delay);
  document.addEventListener("visibilitychange", onChange);
  return () => {
    clearTimeout(first);
    clearInterval(interval);
    document.removeEventListener("visibilitychange", onChange);
  };
}

export default function IranClock() {
  const now = useSyncExternalStore<number | null>(subscribe, minute, serverSnapshot);
  const { formatDate, t } = useLocale();
  if (now === null) return null;
  return <span className={styles.clock}>
    {t("Iran time", "ساعت ایران")}
    <time dateTime={new Date(now).toISOString()}>{formatDate(now, { timeStyle: "short", timeZone: IRAN_TIME_ZONE })}</time>
  </span>;
}
