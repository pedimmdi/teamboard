"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError, deleteCalendarEvent, getCalendarEvent, getProjects, saveCalendarEvent,
  type Project,
  type CalendarEvent, type CalendarEventInput, type CalendarTimelineItem,
} from "@/lib/api";
import ProjectDialog from "@/app/dashboard/workspaces/[slug]/projects/project-dialog";
import { shiftDay, toggleEventDates } from "./calendar-dates";
import styles from "./calendar.module.css";

type Props = {
  token: string;
  slug: string;
  projectId?: string;
  item: CalendarTimelineItem | null;
  day: Date;
  canEditEvent: boolean;
  canDeleteEvent: boolean;
  onClose: () => void;
  onSaved: () => void;
};

const formatDateTime = new Intl.DateTimeFormat("en", {
  dateStyle: "medium", timeStyle: "short", timeZone: "UTC",
});

export default function EventDialog(props: Props) {
  const { token, slug, projectId, item, day, canEditEvent, canDeleteEvent, onClose, onSaved } = props;
  const id = item?.id;
  const [result, setResult] = useState<{ event?: CalendarEvent; error?: string }>();
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState("");
  const [projects, setProjects] = useState<Project[]>();
  const [projectError, setProjectError] = useState("");
  const [dates, setDates] = useState<readonly [string, string]>();
  const [allDay, setAllDay] = useState(item?.all_day ?? false);

  useEffect(() => {
    if (!id || !projectId) return;
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

  useEffect(() => {
    if (projectId) return;
    let cancelled = false;
    async function loadProjects() {
      const options: Project[] = [];
      for (let page = 1; !cancelled; page++) {
        const response = await getProjects(token, slug, page);
        options.push(...response.results);
        if (!response.next) break;
      }
      if (!cancelled) setProjects(options);
    }
    void loadProjects().catch(() => {
      if (!cancelled) setProjectError("Unable to load projects. Please try again.");
    });
    return () => { cancelled = true; };
  }, [token, slug, projectId, revision]);

  const event = result?.event;
  const dayKey = day.toISOString().slice(0, 10);
  const defaultStart = event ? new Date(event.starts_at).toISOString().slice(0, 16) : `${dayKey}T09:00`;
  const defaultEnd = event ? new Date(event.ends_at).toISOString().slice(0, 16) : `${dayKey}T10:00`;

  const [startInput, endInput] = dates ?? (allDay
    ? toggleEventDates(defaultStart, defaultEnd, true)
    : [defaultStart, defaultEnd]);

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    if (busy) return;
    const fields = new FormData(formEvent.currentTarget);
    const start = String(fields.get("start"));
    const end = String(fields.get("end"));
    const startsAt = new Date(allDay ? `${start}T00:00Z` : `${start}Z`);
    const endsAt = allDay ? shiftDay(new Date(`${end}T00:00Z`), 1) : new Date(`${end}Z`);
    const destination = projectId ?? String(fields.get("project") ?? "");
    const title = String(fields.get("title")).trim();
    if (!destination || !title || !(endsAt > startsAt)) {
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
      await saveCalendarEvent(token, slug, destination, data, id);
      onSaved();
    } catch (error) {
      const validation = error instanceof ApiError && error.errors
        ? Object.values(error.errors).flat().join(" ")
        : "";
      setError(validation || (error instanceof Error ? error.message : "Unable to save the event."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!id || !projectId || !canDeleteEvent || busy) return;
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
    <ProjectDialog title={confirmDelete ? "Delete event?" : id ? (canEditEvent ? "Edit event" : item!.title) : "New event"}
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
      ) : !canEditEvent && event ? (
        <div className={styles.form}>
          <p>{event.all_day ? "All day · " : ""}{formatDateTime.format(new Date(event.starts_at))} – {
            formatDateTime.format(event.all_day ? shiftDay(new Date(event.ends_at), -1) : new Date(event.ends_at))
          } UTC</p>
          {event.description && <p className={styles.description}>{event.description}</p>}
          <Link href={`/dashboard/workspaces/${encodeURIComponent(slug)}/projects/${projectId}/calendar`}>Open project calendar</Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={submit}>
          {!projectId && (
            <label>Project
              <select name="project" required defaultValue="" disabled={!projects?.length}>
                <option value="">{projects ? "Select a project" : "Loading projects…"}</option>
                {projects?.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>
          )}
          {projectError && <div role="alert">{projectError} <button type="button" onClick={() => {
            setProjectError("");
            setRevision((value) => value + 1);
          }}>Try again</button></div>}
          {projects?.length === 0 && <p>Create or join a project to add an event.</p>}
          <label>Title<input name="title" required maxLength={200} defaultValue={event?.title} /></label>
          <label>Type<select name="type" defaultValue={event?.event_type ?? "event"}>
            <option value="event">Event</option><option value="meeting">Meeting</option><option value="deadline">Deadline</option>
          </select></label>
          <label className={styles.check}><input type="checkbox" checked={allDay} onChange={(e) => {
            const next = e.target.checked;
            setDates(toggleEventDates(startInput, endInput, next));
            setAllDay(next);
          }} /> All day</label>
          <div className={styles.dateFields}>
            <label>{allDay ? "First day (UTC)" : "Starts at (UTC)"}
              <input key={`start-${allDay}`} required name="start" type={allDay ? "date" : "datetime-local"}
                value={startInput} onChange={(e) => setDates([e.target.value, endInput])} />
            </label>
            <label>{allDay ? "Last day (UTC)" : "Ends at (UTC)"}
              <input key={`end-${allDay}`} required name="end" type={allDay ? "date" : "datetime-local"}
                value={endInput} onChange={(e) => setDates([startInput, e.target.value])} />
            </label>
          </div>
          <label>Description<textarea name="description" rows={3} maxLength={10000} defaultValue={event?.description} /></label>
          <div className={styles.actions}>
            {id && canDeleteEvent && <button type="button" className={styles.danger} disabled={busy}
              onClick={() => { setError(""); setConfirmDelete(true); }}>Delete event</button>}
            <button type="button" disabled={busy} onClick={onClose}>Cancel</button>
            <button className={styles.primary} disabled={busy || (!projectId && !projects?.length)} type="submit">Save event</button>
          </div>
        </form>
      )}
    </ProjectDialog>
  );
}
