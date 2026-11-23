"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, getCalendarTimeline, type CalendarTimelineItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { adjacentMonth, dayOfMonth, itemsForDay, monthDays, monthStart, shiftDay, timelineBounds, weekStart } from "./calendar-dates";
import { iranCivilDay, IRAN_TIME_ZONE } from "@/lib/iran-time";
import { useLocale } from "@/lib/preferences";
import CalendarIcon from "./calendar-icon";
import EventDialog from "./event-dialog";
import IranClock from "./iran-clock";
import styles from "./calendar.module.css";

function today(iranTime: boolean) {
  const today = new Date();
  if (iranTime) return iranCivilDay(today);
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
  const { ui, locale, formatDate, formatNumber } = useWorkspaceLocale();
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const [preferredTimeZone, setPreferredTimeZone] = useState<"utc" | "local" | "tehran" | null>(null);
  const timeZone = preferredTimeZone ?? (locale === "fa" ? "tehran" : "utc");
  const iranTime = timeZone === "tehran";
  const [view, setView] = useState<"month" | "week" | "day">("month");
  const [selectedDate, setSelected] = useState<Date | null>(null);
  const currentDay = today(iranTime);
  const selected = selectedDate ?? currentDay;
  const [filter, setFilter] = useState<"all" | "event" | "task" | "meeting" | "deadline">("all");
  const [revision, setRevision] = useState(0);
  const [dialog, setDialog] = useState<CalendarTimelineItem | "new" | null>(null);
  const [result, setResult] = useState<{ key: string; items?: CalendarTimelineItem[]; error?: string }>();
  const calendar = locale === "fa" ? "persian" : "gregory";
  const firstWeekday = locale === "fa" ? 6 : 1;
  const firstOfMonth = monthStart(selected, calendar);
  const lastOfMonth = adjacentMonth(selected, 1, calendar);
  const firstOfWeek = weekStart(selected, firstWeekday);
  const days = view === "month" ? monthDays(selected, calendar, firstWeekday) : view === "week"
    ? Array.from({ length: 7 }, (_, index) => shiftDay(firstOfWeek, index))
    : [selected];
  const dayLabel = (day: Date) => formatDate(day, { dateStyle: "full", timeZone: "UTC" });
  const monthLabel = formatDate(selected, { month: "long", year: "numeric", timeZone: "UTC" });
  const [start, end] = timelineBounds(days[0], shiftDay(days[days.length - 1], 1), iranTime);
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
    setSelected(adjacentMonth(selected, offset, calendar));
  }
  function refresh() {
    setRevision((value) => value + 1);
  }

  return (
    <section className={styles.calendar} aria-label={ui("Calendar")}>
      <header className={styles.header}>
        <span className={styles.badge}><CalendarIcon /></span>
        <div><h2>{ui("Calendar")}</h2><p>{iranTime ? t("Events in Iran time and task due dates", "رویدادها به وقت ایران و سررسید کارها") : ui("Events and task due dates · Calendar days in UTC")}</p></div>
        {iranTime && <IranClock />}
        {canCreateEvent && <button className={styles.primary} onClick={() => setDialog("new")}>{ui("New event")}</button>}
      </header>
      <div className={styles.panel}>
        <div className={styles.toolbar}>
          <h3 aria-live="polite">{view === "day" ? dayLabel(selected) : monthLabel}</h3>
          <div className={styles.controls}>
            <button aria-label={ui("Previous {0}", ui(view))} onClick={() => changePeriod(-1)}><span aria-hidden="true">‹</span></button>
            <button onClick={() => setSelected(null)}>{ui("Today")}</button>
            <button aria-label={ui("Next {0}", ui(view))} onClick={() => changePeriod(1)}><span aria-hidden="true">›</span></button>
          </div>
          <label className={styles.filter}>{ui("View")}
            <select value={view} onChange={(event) => setView(event.target.value as typeof view)}>
              <option value="month">{ui("Month")}</option>
              <option value="week">{ui("Week")}</option>
              <option value="day">{ui("Day")}</option>
            </select>
          </label>
          <label className={styles.filter}>{ui("Show")}
            <select value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
              <option value="all">{ui("All items")}</option>
              <option value="event">{ui("Events")}</option>
              <option value="meeting">{ui("Meetings")}</option>
              <option value="deadline">{ui("Deadlines")}</option>
              <option value="task">{ui("Task due dates")}</option>
            </select>
          </label>
        </div>
        {!current && <p className={styles.notice} role="status">{ui("Loading calendar…")}</p>}
        {current?.error && <div className={styles.notice} role="alert">
          <p>{ui(current.error)}</p><button onClick={refresh}>{ui("Try again")}</button>
        </div>}
        {view !== "day" && <div className={styles.grid} aria-label={view === "month" ? ui("Month days") : ui("Week days")}>
          {days.slice(0, 7).map((day) => <span key={day.toISOString()} className={styles.weekday}>{formatDate(day, { weekday: "short", timeZone: "UTC" })}</span>)}
          {days.map((day) => {
            const dayItems = itemsForDay(items, day, iranTime);
            return <button key={day.toISOString()} className={styles.day}
              aria-label={ui("{0}, {1} items", dayLabel(day), dayItems.length)}
              aria-pressed={+selected === +day}
              aria-current={+currentDay === +day ? "date" : undefined}
              data-outside={view === "month" && (day < firstOfMonth || day >= lastOfMonth)}
              onClick={() => setSelected(day)}>
              <span className={styles.number}>{formatNumber(dayOfMonth(day, calendar))}</span>
              <span className={styles.preview} aria-hidden="true">{dayItems.slice(0, 2).map((item) =>
                <span key={`${item.item_type}-${item.id}`} data-kind={item.item_type}>{item.title}</span>,
              )}</span>
              {dayItems.length > 0 && <span className={styles.dot} aria-hidden="true" />}
              {dayItems.length > 2 && <span className={styles.more} aria-hidden="true">+{formatNumber(dayItems.length - 2)} {ui("more")}</span>}
            </button>;
          })}
        </div>}
      </div>
      <section className={styles.agenda} aria-label={ui("Day agenda")}>
        <div className={styles.agendaHeader}>
          <h3>{dayLabel(selected)}</h3>
          <label className={styles.filter}>{ui("Event times")}
            <select value={timeZone} onChange={(event) => setPreferredTimeZone(event.target.value as typeof timeZone)}>
              <option value="utc">UTC</option>
              <option value="local">{ui("Local time")}</option>
              <option value="tehran">{t("Iran time", "وقت ایران")}</option>
            </select>
          </label>
        </div>
        {current?.items && (() => {
          const dayItems = itemsForDay(items, selected, iranTime);
          return dayItems.length ? <ul>{dayItems.map((item) => (
            <li key={`${item.item_type}-${item.id}`}>
              <span className={styles.kind} data-kind={item.item_type}>
                {item.item_type === "task" ? ui("Task due") : ui(item.event_type ?? "event")}
              </span>
              {item.item_type === "task" ? (
                <Link href={`${workspacePath}/projects/${item.project}/tasks?task=${item.id}`}>{item.title}</Link>
              ) : (
                <button onClick={() => setDialog(item)}>{item.title}</button>
              )}
              <time dateTime={item.starts_at}>{item.all_day ? ui("All day") : formatDate(item.starts_at, {
                timeStyle: "short",
                timeZone: iranTime ? IRAN_TIME_ZONE : timeZone === "local" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC",
              })}</time>
            </li>
          ))}</ul> : <p>{ui("No items for this day.")}</p>;
        })()}
      </section>
      {dialog && accessToken && (
        <EventDialog token={accessToken} slug={slug} projectId={dialog === "new" ? projectId : dialog.project}
          item={dialog === "new" ? null : dialog} day={selected} iranTime={iranTime} canEditEvent={canEditEvent} canDeleteEvent={canDeleteEvent}
          onClose={() => setDialog(null)} onSaved={() => { setDialog(null); refresh(); }} />
      )}
    </section>
  );
}
