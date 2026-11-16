"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, getCalendarTimeline, type CalendarTimelineItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { itemsForDay, monthDays, shiftDay } from "./calendar-dates";
import CalendarIcon from "./calendar-icon";
import EventDialog from "./event-dialog";
import styles from "./calendar.module.css";

const monthLabel = new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" });
const dayLabel = new Intl.DateTimeFormat("en", { dateStyle: "full", timeZone: "UTC" });
const timeLabel = new Intl.DateTimeFormat("en", { timeStyle: "short", timeZone: "UTC" });
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
function todayUtc() {
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  return today;
}

export default function CalendarView({ slug, projectId, canManage = false }: {
  slug: string;
  projectId?: string;
  canManage?: boolean;
}) {
  const { accessToken } = useAuth();
  const [selected, setSelected] = useState(todayUtc);
  const [filter, setFilter] = useState<"all" | "event" | "task">("all");
  const [revision, setRevision] = useState(0);
  const [dialog, setDialog] = useState<CalendarTimelineItem | "new" | null>(null);
  const [result, setResult] = useState<{ key: string; items?: CalendarTimelineItem[]; error?: string }>();
  const days = monthDays(selected);
  const start = days[0].toISOString();
  const end = shiftDay(days[41], 1).toISOString();
  const key = JSON.stringify([slug, projectId, start, revision]);
  const current = result?.key === key ? result : undefined;

  useEffect(() => {
    if (!accessToken) return;
    const controller = new AbortController();
    getCalendarTimeline(accessToken, slug, start, end, projectId, controller.signal)
      .then(({ results }) => {
        if (!controller.signal.aborted) setResult({ key, items: results });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          const rangeError = error instanceof ApiError ? error.errors?.date_range : undefined;
          setResult({
            key,
            error: (Array.isArray(rangeError) ? rangeError[0] : rangeError)
              || (error instanceof Error ? error.message : "Unable to load the calendar."),
          });
        }
      });
    return () => controller.abort();
  }, [accessToken, slug, projectId, start, end, key]);

  const items = (current?.items ?? []).filter((item) => filter === "all" || item.item_type === filter);
  const workspacePath = `/dashboard/workspaces/${encodeURIComponent(slug)}`;
  function changeMonth(offset: number) {
    setSelected(new Date(Date.UTC(selected.getUTCFullYear(), selected.getUTCMonth() + offset, 1)));
  }
  function refresh() {
    setRevision((value) => value + 1);
  }

  return (
    <section className={styles.calendar} aria-label="Calendar">
      <header className={styles.header}>
        <span className={styles.badge}><CalendarIcon /></span>
        <div><h2>Calendar</h2><p>Events and task due dates · UTC</p></div>
        {canManage && <button className={styles.primary} onClick={() => setDialog("new")}>New event</button>}
      </header>
      <div className={styles.panel}>
        <div className={styles.toolbar}>
          <h3 aria-live="polite">{monthLabel.format(selected)}</h3>
          <div className={styles.controls}>
            <button aria-label="Previous month" onClick={() => changeMonth(-1)}>‹</button>
            <button onClick={() => setSelected(todayUtc())}>Today</button>
            <button aria-label="Next month" onClick={() => changeMonth(1)}>›</button>
          </div>
          <label className={styles.filter}>Show
            <select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
              <option value="all">All items</option>
              <option value="event">Events</option>
              <option value="task">Task due dates</option>
            </select>
          </label>
        </div>
        {!current && <p className={styles.notice} role="status">Loading calendar…</p>}
        {current?.error && <div className={styles.notice} role="alert">
          <p>{current.error}</p><button onClick={refresh}>Try again</button>
        </div>}
        <div className={styles.grid} aria-label="Month days">
          {weekdayLabels.map((day) => <span key={day} className={styles.weekday}>{day}</span>)}
          {days.map((day) => {
            const dayItems = itemsForDay(items, day);
            return <button key={day.toISOString()} className={styles.day}
              aria-label={`${dayLabel.format(day)}, ${dayItems.length} items`}
              aria-pressed={+selected === +day}
              aria-current={+todayUtc() === +day ? "date" : undefined}
              data-outside={day.getUTCMonth() !== selected.getUTCMonth()}
              onClick={() => setSelected(day)}>
              <span className={styles.number}>{day.getUTCDate()}</span>
              <span className={styles.preview} aria-hidden="true">{dayItems.slice(0, 2).map((item) =>
                <span key={`${item.item_type}-${item.id}`} data-kind={item.item_type}>{item.title}</span>,
              )}</span>
              {dayItems.length > 0 && <span className={styles.dot} aria-hidden="true" />}
              {dayItems.length > 2 && <span className={styles.more} aria-hidden="true">+{dayItems.length - 2} more</span>}
            </button>;
          })}
        </div>
      </div>
      <section className={styles.agenda} aria-label="Day agenda">
        <h3>{dayLabel.format(selected)}</h3>
        {current?.items && (() => {
          const dayItems = itemsForDay(items, selected);
          return dayItems.length ? <ul>{dayItems.map((item) => (
            <li key={`${item.item_type}-${item.id}`}>
              <span className={styles.kind} data-kind={item.item_type}>
                {item.item_type === "task" ? "Task due" : item.event_type}
              </span>
              {item.item_type === "task" ? (
                <Link href={`${workspacePath}/projects/${item.project}/tasks?task=${item.id}`}>{item.title}</Link>
              ) : (
                <button onClick={() => setDialog(item)}>{item.title}</button>
              )}
              <time dateTime={item.starts_at}>{item.all_day ? "All day" : timeLabel.format(new Date(item.starts_at))}</time>
            </li>
          ))}</ul> : <p>No items for this day.</p>;
        })()}
      </section>
      {dialog && accessToken && (
        <EventDialog token={accessToken} slug={slug} projectId={dialog === "new" ? projectId! : dialog.project}
          item={dialog === "new" ? null : dialog} day={selected} canManage={canManage}
          onClose={() => setDialog(null)} onSaved={() => { setDialog(null); refresh(); }} />
      )}
    </section>
  );
}
