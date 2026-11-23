"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError, deleteCalendarEvent, getCalendarEvent, getProjects, saveCalendarEvent,
  type Project,
  type CalendarEvent, type CalendarEventInput, type CalendarTimelineItem,
} from "@/lib/api";
import ProjectDialog from "@/app/dashboard/workspaces/[slug]/projects/project-dialog";
import { iranInstant, iranWallClock, IRAN_TIME_ZONE } from "@/lib/iran-time";
import { useLocale } from "@/lib/preferences";
import { shiftDay, toggleEventDates } from "./calendar-dates";
import styles from "./calendar.module.css";

type Props = {
  token: string;
  slug: string;
  projectId?: string;
  item: CalendarTimelineItem | null;
  day: Date;
  iranTime: boolean;
  canEditEvent: boolean;
  canDeleteEvent: boolean;
  onClose: () => void;
  onSaved: () => void;
};

export default function EventDialog(props: Props) {
  const { ui, formatDate } = useWorkspaceLocale();
  const { t } = useLocale();
  const { token, slug, projectId, item, day, iranTime, canEditEvent, canDeleteEvent, onClose, onSaved } = props;
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
  const eventInput = (instant: string) => iranTime && !event?.all_day ? iranWallClock(instant) : new Date(instant).toISOString().slice(0, 16);
  const defaultStart = event ? eventInput(event.starts_at) : `${dayKey}T09:00`;
  const defaultEnd = event ? eventInput(event.ends_at) : `${dayKey}T10:00`;

  const [startInput, endInput] = dates ?? (allDay
    ? toggleEventDates(defaultStart, defaultEnd, true)
    : [defaultStart, defaultEnd]);

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    if (busy) return;
    const fields = new FormData(formEvent.currentTarget);
    const start = String(fields.get("start"));
    const end = String(fields.get("end"));
    const timedInstant = (input: string) => iranTime ? iranInstant(input) : new Date(`${input}Z`);
    const startsAt = allDay ? new Date(`${start}T00:00Z`) : timedInstant(start);
    const endsAt = allDay ? shiftDay(new Date(`${end}T00:00Z`), 1) : timedInstant(end);
    const destination = projectId ?? String(fields.get("project") ?? "");
    const title = String(fields.get("title")).trim();
    if (!destination || !title || !startsAt || !endsAt || !(endsAt > startsAt)) {
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
    <ProjectDialog title={confirmDelete ? ui("Delete event?") : id ? (canEditEvent ? ui("Edit event") : item!.title) : ui("New event")}
      onClose={onClose} busy={busy}>
      {error && <p role="alert" className={styles.error}>{ui(error)}</p>}
      {confirmDelete ? (
        <div className={styles.form}>
          <p>{ui("This will remove “")}{event?.title}{ui("” from the calendar.")}</p>
          <div className={styles.actions}>
            <button disabled={busy} onClick={() => setConfirmDelete(false)}>{ui("Cancel")}</button>
            <button className={styles.danger} disabled={busy} onClick={() => void remove()}>{ui("Delete event")}</button>
          </div>
        </div>
      ) : id && !event ? (
        <div className={styles.form}>
          {result?.error ? <><p role="alert">{ui(result.error)}</p><button onClick={() => {
            setResult(undefined);
            setRevision((value) => value + 1);
          }}>{ui("Try again")}</button></> : <p role="status">{ui("Loading event…")}</p>}
        </div>
      ) : !canEditEvent && event ? (
        <div className={styles.form}>
          <p>{event.all_day ? ui("All day · ") : ""}{formatDate(event.starts_at, {
            dateStyle: "medium", timeStyle: event.all_day ? undefined : "short", timeZone: iranTime && !event.all_day ? IRAN_TIME_ZONE : "UTC",
          })} – {formatDate(event.all_day ? shiftDay(new Date(event.ends_at), -1) : event.ends_at, {
            dateStyle: "medium", timeStyle: event.all_day ? undefined : "short", timeZone: iranTime && !event.all_day ? IRAN_TIME_ZONE : "UTC",
          })}{!event.all_day && <> · {iranTime ? t("Iran time", "وقت ایران") : "UTC"}</>}</p>
          {event.description && <p className={styles.description}>{event.description}</p>}
          <Link href={`/dashboard/workspaces/${encodeURIComponent(slug)}/projects/${projectId}/calendar`}>{ui("Open project calendar")}</Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={submit}>
          {!projectId && (
            <label>{ui("Project")}
              <select name="project" required defaultValue="" disabled={!projects?.length}>
                <option value="">{projects ? ui("Select a project") : ui("Loading projects…")}</option>
                {projects?.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>
          )}
          {projectError && <div role="alert">{ui(projectError)} <button type="button" onClick={() => {
            setProjectError("");
            setRevision((value) => value + 1);
          }}>{ui("Try again")}</button></div>}
          {projects?.length === 0 && <p>{ui("Create or join a project to add an event.")}</p>}
          <label>{ui("Title")}<input name="title" required maxLength={200} defaultValue={event?.title} /></label>
          <label>{ui("Type")}<select name="type" defaultValue={event?.event_type ?? "event"}>
            <option value="event">{ui("Event")}</option><option value="meeting">{ui("Meeting")}</option><option value="deadline">{ui("Deadline")}</option>
          </select></label>
          <label className={styles.check}><input type="checkbox" checked={allDay} onChange={(e) => {
            const next = e.target.checked;
            setDates(toggleEventDates(startInput, endInput, next));
            setAllDay(next);
          }} /> {ui("All day")}</label>
          <div className={styles.dateFields}>
            <label>{allDay ? ui("First day (UTC)") : iranTime ? t("Starts at (Iran time)", "شروع (به وقت ایران)") : ui("Starts at (UTC)")}
              <input key={`start-${allDay}`} required name="start" type={allDay ? "date" : "datetime-local"}
                value={startInput} onChange={(e) => setDates([e.target.value, endInput])} />
            </label>
            <label>{allDay ? ui("Last day (UTC)") : iranTime ? t("Ends at (Iran time)", "پایان (به وقت ایران)") : ui("Ends at (UTC)")}
              <input key={`end-${allDay}`} required name="end" type={allDay ? "date" : "datetime-local"}
                value={endInput} onChange={(e) => setDates([startInput, e.target.value])} />
            </label>
          </div>
          <label>{ui("Description")}<textarea name="description" rows={3} maxLength={10000} defaultValue={event?.description} /></label>
          <div className={styles.actions}>
            {id && canDeleteEvent && <button type="button" className={styles.danger} disabled={busy}
              onClick={() => { setError(""); setConfirmDelete(true); }}>{ui("Delete event")}</button>}
            <button type="button" disabled={busy} onClick={onClose}>{ui("Cancel")}</button>
            <button className={styles.primary} disabled={busy || (!projectId && !projects?.length)} type="submit">{ui("Save event")}</button>
          </div>
        </form>
      )}
    </ProjectDialog>
  );
}
