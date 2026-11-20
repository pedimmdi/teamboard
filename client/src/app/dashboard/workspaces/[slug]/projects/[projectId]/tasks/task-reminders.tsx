"use client";

import {useEffect, useId, useRef, useState, type FormEvent} from "react";
import {getTaskReminders, saveTaskReminder, cancelTaskReminder, ApiError, type TaskReminder, type Task, type ReminderInput} from "@/lib/api";
import {useTransientMessage} from "@/hooks/use-transient-message";
import {reminderLocalInput, futureReminderTime} from "./reminder-utils";
import styles from "./reminders.module.css";

function errorText(error: unknown) {
  return error instanceof ApiError && error.errors ? Object.values(error.errors).flat().join(" ") : error instanceof Error ? error.message : "Unable to manage reminders.";
}
export default function TaskReminders({token, slug, projectId, task, onBusyChange}: {
  token: string; slug: string; projectId: string; task: Task; onBusyChange: (busy: boolean) => void;
}) {
  const [rows, setRows] = useState<TaskReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useTransientMessage<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<TaskReminder | null>(null);
  const [form, setForm] = useState(false);
  const [kind, setKind] = useState<"absolute" | "relative">("absolute");
  const [zone, setZone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [date, setDate] = useState("");
  const [days, setDays] = useState(0);
  const [clock, setClock] = useState("09:00");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const id = useId();
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const result = await getTaskReminders(token, slug, projectId, task.id, page, controller.signal);
        if (!controller.signal.aborted) {setRows((current) => page === 1 ? result.results : [...new Map([...current, ...result.results].map((row) => [row.id, row])).values()]); setHasMore(Boolean(result.next)); setError("");}
      } catch (error) {if (!controller.signal.aborted) setError(errorText(error));}
      finally {if (!controller.signal.aborted) setLoading(false);}
    }
    void load();
    return () => controller.abort();
  }, [token, slug, projectId, task.id, task.updated_at, task.due_date, page, revision]);
  const active = rows.filter((row) => ["pending", "disabled", "invalid", "failed"].includes(row.status)).length;
  function open(row?: TaskReminder) {
    setEditing(row ?? null); setForm(true); setError("");
    setKind(row?.kind ?? "absolute"); setZone(row?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC");
    setDate(row?.run_at ? reminderLocalInput(row.run_at, row.timezone) : "");
    setDays(row?.days_before ?? 0); setClock(row?.local_time?.slice(0, 5) ?? "09:00");
  }
  async function action(work: () => Promise<unknown>, message: string) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); onBusyChange(true); setError(""); setSuccess(null);
    try {await work(); setSuccess(message); setForm(false); setPage(1); setRevision((value) => value + 1);}
    catch (error) {setError(errorText(error));}
    finally {busyRef.current = false; setBusy(false); onBusyChange(false);}
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    let input: ReminderInput;
    if (kind === "absolute") {
      try {
        const iso = futureReminderTime(date, zone);
        input = {kind, timezone: zone, run_at: iso};
      } catch (error) {setError(errorText(error)); return;}
    } else input = {kind, timezone: zone, days_before: days, local_time: clock};
    await action(() => saveTaskReminder(token, slug, projectId, task.id, input, editing?.id), editing ? "Reminder updated." : "Reminder created.");
  }
  function time(row: TaskReminder) {
    if (!row.run_at) return "Waiting for a due date";
    try {return new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short", timeZone: row.timezone}).format(new Date(row.run_at)) + ` (${row.timezone})`;}
    catch {return row.run_at;}
  }
  return <section className={styles.section} aria-label="Reminders">
    <header><h3>Reminders</h3><span>Private to you · up to 3 active</span></header>
    {loading && <p role="status">Loading reminders…</p>}
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => setRevision((value) => value + 1)}>Retry reminders</button></div>}
    {success && <p role="status">{success}</p>}
    {!loading && !rows.length && <p>No reminders yet. Schedule a private notification for this task.</p>}
    <ul>{rows.map((row) => <li key={row.id}>
      <strong>{time(row)}</strong><small>{row.kind === "relative" ? `${row.days_before} day(s) before due date at ${row.local_time?.slice(0,5)}` : "Fixed time"} · {row.status}</small>
      {row.status === "invalid" && <p>Choose another time. The due date changed or the local time is invalid.</p>}
      {row.status === "failed" && <p>Delivery will retry automatically. You can also reschedule.</p>}
      {["pending", "disabled", "invalid", "failed"].includes(row.status) && <div className={styles.actions}>
        <button type="button" disabled={busy} onClick={() => open(row)}>Edit reminder</button>
        <button type="button" disabled={busy} onClick={() => void action(() => cancelTaskReminder(token, slug, projectId, task.id, row.id), "Reminder cancelled.")}>Cancel reminder</button>
      </div>}
    </li>)}</ul>
    {hasMore && <button type="button" disabled={busy} onClick={() => setPage((value) => value + 1)}>Load more reminders</button>}
    {!form && <button type="button" className={styles.newReminder} disabled={busy || loading || active >= 3 || task.status === "done"} onClick={() => open()}>New reminder</button>}
    {task.status === "done" && <p>Reopen this task to schedule a new reminder.</p>}
    {form && <form onSubmit={submit} className={styles.form}>
      <label htmlFor={id+"kind"}>Reminder type</label><select id={id+"kind"} disabled={busy} value={kind} onChange={(event) => setKind(event.target.value as "absolute" | "relative")}><option value="absolute">Fixed date and time</option><option value="relative" disabled={!task.due_date}>Relative to due date</option></select>
      <label htmlFor={id+"zone"}>Timezone (IANA)</label><input id={id+"zone"} required maxLength={64} disabled={busy} value={zone} onChange={(event) => setZone(event.target.value)} list={id+"zones"}/>
      <datalist id={id+"zones"}>{["UTC","Asia/Tehran","Europe/London","Europe/Paris","America/New_York","Asia/Tokyo"].map((value) => <option key={value} value={value}/>)}</datalist>
      {kind === "absolute" ? <><label htmlFor={id+"date"}>Reminder date and time</label><input id={id+"date"} type="datetime-local" required disabled={busy} value={date} onChange={(event) => setDate(event.target.value)}/><small>Enter time in the selected timezone. Changing timezone keeps the entered wall-clock time.</small></> : <>
        <label htmlFor={id+"preset"}>Due date preset</label><select id={id+"preset"} value={days} disabled={busy} onChange={(event) => setDays(Number(event.target.value))}><option value={0}>On the due date</option><option value={1}>One day before</option><option value={3}>Three days before</option><option value={7}>One week before</option>{![0,1,3,7].includes(days) && <option value={days}>{days} days before</option>}</select>
        <label htmlFor={id+"days"}>Days before due date</label><input id={id+"days"} type="number" min={0} max={365} required value={days} disabled={busy} onChange={(event) => setDays(Number(event.target.value))}/>
        <label htmlFor={id+"clock"}>Local reminder time</label><input id={id+"clock"} type="time" required disabled={busy} value={clock} onChange={(event) => setClock(event.target.value)}/><small>Due dates have no deadline hour. Default: 09:00 in the selected timezone. Invalid or ambiguous DST times must be changed.</small>
      </>}
      <div className={styles.actions}><button disabled={busy}>{busy ? "Saving…" : editing ? "Save reminder" : "Create reminder"}</button><button type="button" disabled={busy} onClick={() => setForm(false)}>Close reminder form</button></div>
    </form>}
  </section>;
}
