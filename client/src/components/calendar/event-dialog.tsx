"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  deleteCalendarEvent, getCalendarEvent, saveCalendarEvent,
  type CalendarEvent, type CalendarEventInput, type CalendarTimelineItem,
} from "@/lib/api";
import ProjectDialog from "@/app/dashboard/workspaces/[slug]/projects/project-dialog";
import { shiftDay } from "./calendar-dates";
import styles from "./calendar.module.css";

type Props = {
  token: string;
  slug: string;
  projectId: string;
  item: CalendarTimelineItem | null;
  day: Date;
  canManage: boolean;
  onClose: () => void;
  onSaved: () => void;
};

const formatDateTime = new Intl.DateTimeFormat("en", {
  dateStyle: "medium", timeStyle: "short", timeZone: "UTC",
});

export default function EventDialog(props: Props) {
  const { token, slug, projectId, item, day, canManage, onClose, onSaved } = props;
  const id = item?.id;
  const [result, setResult] = useState<{ event?: CalendarEvent; error?: string }>();
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState("");
  const [allDay, setAllDay] = useState(item?.all_day ?? false);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    getCalendarEvent(token, slug, projectId, id, controller.signal)
      .then((event) => {
        if (!controller.signal.aborted) {
          setAllDay(event.all_day);
          setResult({ event });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({ error: error instanceof Error ? error.message : "Unable to load the event." });
        }
      });
    return () => controller.abort();
  }, [token, slug, projectId, id, revision]);

  const event = result?.event;
  const dayKey = day.toISOString().slice(0, 10);
  const defaultStart = event ? new Date(event.starts_at).toISOString().slice(0, 16) : `${dayKey}T09:00`;
  const defaultEnd = event ? new Date(event.ends_at).toISOString().slice(0, 16) : `${dayKey}T10:00`;

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    if (busy) return;
    const fields = new FormData(formEvent.currentTarget);
    const start = String(fields.get("start"));
    const end = String(fields.get("end"));
    const startsAt = new Date(allDay ? `${start}T00:00Z` : `${start}Z`);
    const endsAt = allDay ? shiftDay(new Date(`${end}T00:00Z`), 1) : new Date(`${end}Z`);
    const title = String(fields.get("title")).trim();
    if (!title || !(endsAt > startsAt)) {
      setError("Enter a title and an end after the start.");
      return;
    }

    const data: CalendarEventInput = {
      title,
      description: String(fields.get("description")),
      event_type: fields.get("type") as CalendarEventInput["event_type"],
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
      all_day: allDay,
    };
    setBusy(true);
    setError("");
    try {
      await saveCalendarEvent(token, slug, projectId, data, id);
      onSaved();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save the event.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!id || busy) return;
    setBusy(true);
    setError("");
    try {
      await deleteCalendarEvent(token, slug, projectId, id);
      onSaved();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to delete the event.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ProjectDialog title={confirmDelete ? "Delete event?" : id ? (canManage ? "Edit event" : item!.title) : "New event"}
      onClose={onClose} busy={busy}>
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {confirmDelete ? (
        <div className={styles.form}>
          <p>This will remove “{event?.title}” from the calendar.</p>
          <div className={styles.actions}>
            <button disabled={busy} onClick={() => setConfirmDelete(false)}>Cancel</button>
            <button className={styles.danger} disabled={busy} onClick={() => void remove()}>Delete event</button>
          </div>
        </div>
      ) : id && !event ? (
        <div className={styles.form}>
          {result?.error ? <><p role="alert">{result.error}</p><button onClick={() => {
            setResult(undefined);
            setRevision((value) => value + 1);
          }}>Try again</button></> : <p role="status">Loading event…</p>}
        </div>
      ) : !canManage && event ? (
        <div className={styles.form}>
          <p>{event.all_day ? "All day · " : ""}{formatDateTime.format(new Date(event.starts_at))} – {
            formatDateTime.format(event.all_day ? shiftDay(new Date(event.ends_at), -1) : new Date(event.ends_at))
          } UTC</p>
          {event.description && <p className={styles.description}>{event.description}</p>}
          <Link href={`/dashboard/workspaces/${encodeURIComponent(slug)}/projects/${projectId}/calendar`}>Open project calendar</Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={submit}>
          <label>Title<input name="title" required maxLength={200} defaultValue={event?.title} /></label>
          <label>Type<select name="type" defaultValue={event?.event_type ?? "event"}>
            <option value="event">Event</option><option value="meeting">Meeting</option><option value="deadline">Deadline</option>
          </select></label>
          <label className={styles.check}><input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} /> All day</label>
          <div className={styles.dateFields}>
            <label>{allDay ? "First day (UTC)" : "Starts at (UTC)"}
              <input key={`start-${allDay}`} required name="start" type={allDay ? "date" : "datetime-local"}
                defaultValue={allDay ? defaultStart.slice(0, 10) : defaultStart} />
            </label>
            <label>{allDay ? "Last day (UTC)" : "Ends at (UTC)"}
              <input key={`end-${allDay}`} required name="end" type={allDay ? "date" : "datetime-local"}
                defaultValue={allDay && event?.all_day
                  ? shiftDay(new Date(event.ends_at), -1).toISOString().slice(0, 10)
                  : allDay ? defaultEnd.slice(0, 10) : defaultEnd} />
            </label>
          </div>
          <label>Description<textarea name="description" rows={3} maxLength={10000} defaultValue={event?.description} /></label>
          <div className={styles.actions}>
            {id && <button type="button" className={styles.danger} disabled={busy}
              onClick={() => { setError(""); setConfirmDelete(true); }}>Delete event</button>}
            <button type="button" disabled={busy} onClick={onClose}>Cancel</button>
            <button className={styles.primary} disabled={busy} type="submit">Save event</button>
          </div>
        </form>
      )}
    </ProjectDialog>
  );
}
