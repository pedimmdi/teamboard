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
const localTimeLabel = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });
const timeLabel = new Intl.DateTimeFormat("en", { timeStyle: "short", timeZone: "UTC" });
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
function todayUtc() {
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  return today;
}

export default function CalendarView({ slug, projectId, canCreateEvent = false, canEditEvent = false, canDeleteEvent = false }: {
  slug: string;
  projectId?: string;
  canCreateEvent?: boolean;
  canEditEvent?: boolean;
  canDeleteEvent?: boolean;
}) {
  const { accessToken } = useAuth();
  const [localTimes, setLocalTimes] = useState(false);
  const [view, setView] = useState<"month" | "week" | "day">("month");
  const [selected, setSelected] = useState(todayUtc);
  const [filter, setFilter] = useState<"all" | "event" | "task" | "meeting" | "deadline">("all");
  const [revision, setRevision] = useState(0);
  const [dialog, setDialog] = useState<CalendarTimelineItem | "new" | null>(null);
  const [result, setResult] = useState<{ key: string; items?: CalendarTimelineItem[]; error?: string }>();
  const monday = shiftDay(selected, -((selected.getUTCDay() + 6) % 7));
  const days = view === "month" ? monthDays(selected) : view === "week"
    ? Array.from({ length: 7 }, (_, index) => shiftDay(monday, index))
    : [selected];
  const start = days[0].toISOString();
  const end = shiftDay(days[days.length - 1], 1).toISOString();
  const key = JSON.stringify([slug, projectId, start, end, revision]);
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

  const items = (current?.items ?? []).filter((item) => filter === "all" || item.item_type === filter || item.event_type === filter);
  const workspacePath = `/dashboard/workspaces/${encodeURIComponent(slug)}`;
  function changePeriod(offset: number) {
    if (view !== "month") {
      setSelected(shiftDay(selected, offset * (view === "week" ? 7 : 1)));
      return;
    }
    setSelected(new Date(Date.UTC(selected.getUTCFullYear(), selected.getUTCMonth() + offset, 1)));
  }
  function refresh() {
    setRevision((value) => value + 1);
  }

  return (
    <section className={styles.calendar} aria-label="Calendar">
      <header className={styles.header}>
        <span className={styles.badge}><CalendarIcon /></span>
        <div><h2>Calendar</h2><p>Events and task due dates · Calendar days in UTC</p></div>
        {canCreateEvent && <button className={styles.primary} onClick={() => setDialog("new")}>New event</button>}
      </header>
      <div className={styles.panel}>
        <div className={styles.toolbar}>
          <h3 aria-live="polite">{view === "day" ? dayLabel.format(selected) : monthLabel.format(selected)}</h3>
          <div className={styles.controls}>
            <button aria-label={`Previous ${view}`} onClick={() => changePeriod(-1)}>‹</button>
            <button onClick={() => setSelected(todayUtc())}>Today</button>
            <button aria-label={`Next ${view}`} onClick={() => changePeriod(1)}>›</button>
          </div>
          <label className={styles.filter}>View
            <select value={view} onChange={(event) => setView(event.target.value as typeof view)}>
              <option value="month">Month</option>
              <option value="week">Week</option>
              <option value="day">Day</option>
            </select>
          </label>
          <label className={styles.filter}>Show
            <select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
              <option value="all">All items</option>
              <option value="event">Events</option>
              <option value="meeting">Meetings</option>
              <option value="deadline">Deadlines</option>
              <option value="task">Task due dates</option>
            </select>
          </label>
        </div>
        {!current && <p className={styles.notice} role="status">Loading calendar…</p>}
        {current?.error && <div className={styles.notice} role="alert">
          <p>{current.error}</p><button onClick={refresh}>Try again</button>
        </div>}
        {view !== "day" && <div className={styles.grid} aria-label={view === "month" ? "Month days" : "Week days"}>
          {weekdayLabels.map((day) => <span key={day} className={styles.weekday}>{day}</span>)}
          {days.map((day) => {
            const dayItems = itemsForDay(items, day);
            return <button key={day.toISOString()} className={styles.day}
              aria-label={`${dayLabel.format(day)}, ${dayItems.length} items`}
              aria-pressed={+selected === +day}
              aria-current={+todayUtc() === +day ? "date" : undefined}
              data-outside={view === "month" && day.getUTCMonth() !== selected.getUTCMonth()}
              onClick={() => setSelected(day)}>
              <span className={styles.number}>{day.getUTCDate()}</span>
              <span className={styles.preview} aria-hidden="true">{dayItems.slice(0, 2).map((item) =>
                <span key={`${item.item_type}-${item.id}`} data-kind={item.item_type}>{item.title}</span>,
              )}</span>
              {dayItems.length > 0 && <span className={styles.dot} aria-hidden="true" />}
              {dayItems.length > 2 && <span className={styles.more} aria-hidden="true">+{dayItems.length - 2} more</span>}
            </button>;
          })}
        </div>}
      </div>
      <section className={styles.agenda} aria-label="Day agenda">
        <div className={styles.agendaHeader}>
          <h3>{dayLabel.format(selected)}</h3>
          <label className={styles.filter}>Event times
            <select value={localTimes ? "local" : "utc"} onChange={(event) => setLocalTimes(event.target.value === "local")}>
              <option value="utc">UTC</option>
              <option value="local">Local time</option>
            </select>
          </label>
        </div>
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
              <time dateTime={item.starts_at}>{item.all_day ? "All day" : (localTimes ? localTimeLabel : timeLabel).format(new Date(item.starts_at))}</time>
            </li>
          ))}</ul> : <p>No items for this day.</p>;
        })()}
      </section>
      {dialog && accessToken && (
        <EventDialog token={accessToken} slug={slug} projectId={dialog === "new" ? projectId : dialog.project}
          item={dialog === "new" ? null : dialog} day={selected} canEditEvent={canEditEvent} canDeleteEvent={canDeleteEvent}
          onClose={() => setDialog(null)} onSaved={() => { setDialog(null); refresh(); }} />
      )}
    </section>
  );
}
