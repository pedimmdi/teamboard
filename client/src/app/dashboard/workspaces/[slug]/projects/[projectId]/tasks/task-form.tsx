"use client";

import { useId, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, type ProjectMember, type TaskInput } from "@/lib/api";
import AssigneePicker from "./assignee-picker";
import { taskPriorities, taskStatuses, overdueDays } from "./task-utils";
import styles from "./tasks.module.css";

export default function TaskForm({
  initial,
  members,
  membersLoading,
  membersError,
  onRetryMembers,
  onSubmit,
  onCancel,
  onBusyChange,
  editing = false,
  metadata,
  deleteAction,
}: {
  initial: TaskInput;
  members: ProjectMember[];
  membersLoading: boolean;
  membersError: string;
  onRetryMembers: () => void;
  onSubmit: (input: TaskInput) => Promise<void>;
  onCancel: () => void;
  onBusyChange: (busy: boolean) => void;
  editing?: boolean;
  metadata?: ReactNode;
  deleteAction?: ReactNode;
}) {
  const [input, setInput] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const id = useId();
  const days = overdueDays(input.due_date, input.status);
  const changed =
    JSON.stringify({ ...input, title: input.title.trim() }) !==
    JSON.stringify(initial);
  function update<K extends keyof TaskInput>(key: K, value: TaskInput[K]) {
    setInput((current) => ({ ...current, [key]: value }));
    setFields((current) => ({ ...current, [key]: "" }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!input.title.trim()) {
      setFields({ title: "Task title cannot be empty." });
      return;
    }
    setBusy(true);
    onBusyChange(true);
    setError("");
    setFields({});
    try {
      await onSubmit({ ...input, title: input.title.trim() });
    } catch (err) {
      const next: Record<string, string> = {};
      if (err instanceof ApiError && err.errors)
        for (const key of Object.keys(input)) {
          const message = err.errors[key];
          if (message)
            next[key] = Array.isArray(message) ? message.join(" ") : message;
        }
      setFields(next);
      if (!Object.keys(next).length)
        setError(err instanceof Error ? err.message : "Unable to save task.");
    } finally {
      setBusy(false);
      onBusyChange(false);
    }
  }
  const fieldError = (key: keyof TaskInput) =>
    fields[key] ? (
      <p id={`${id}-${key}-error`} className={styles.error} role="alert">
        {fields[key]}
      </p>
    ) : null;
  const title = (
    <div className={styles.field}>
      <label htmlFor={`${id}-title`}>Title</label>
      <input
        id={`${id}-title`}
        value={input.title}
        maxLength={200}
        placeholder="What needs to be done?"
        disabled={busy}
        onChange={(event) => update("title", event.target.value)}
        aria-invalid={Boolean(fields.title)}
        aria-describedby={fields.title ? `${id}-title-error` : undefined}
      />
      {fieldError("title")}
    </div>
  );
  const description = (
    <div className={styles.field}>
      <label htmlFor={`${id}-description`}>
        Description{!editing && " (optional)"}
      </label>
      <textarea
        id={`${id}-description`}
        value={input.description}
        maxLength={10000}
        disabled={busy}
        placeholder="Add more details…"
        onChange={(event) => update("description", event.target.value)}
        aria-invalid={Boolean(fields.description)}
        aria-describedby={`${id}-count${fields.description ? ` ${id}-description-error` : ""}`}
      />
      <span className={styles.counter} id={`${id}-count`}>
        {input.description.length} / 10000
      </span>
      {fieldError("description")}
    </div>
  );
  return (
    <form className={styles.form} onSubmit={submit}>
      {error && (
        <p className={styles.alert} role="alert">
          {error}
        </p>
      )}
      {title}
      {!editing && description}
      <div className={styles.formGrid}>
        <div className={styles.field}>
          <label htmlFor={`${id}-status`}>Status</label>
          <select
            id={`${id}-status`}
            value={input.status}
            disabled={busy}
            onChange={(event) =>
              update("status", event.target.value as TaskInput["status"])
            }
          >
            {taskStatuses.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
          {fieldError("status")}
        </div>
        <div className={styles.field}>
          <label htmlFor={`${id}-priority`}>Priority</label>
          <select
            id={`${id}-priority`}
            value={input.priority}
            disabled={busy}
            onChange={(event) =>
              update("priority", event.target.value as TaskInput["priority"])
            }
          >
            {taskPriorities.map((priority) => (
              <option key={priority} value={priority}>
                {priority.charAt(0).toUpperCase() + priority.slice(1)}
              </option>
            ))}
          </select>
          {fieldError("priority")}
        </div>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>Assignee</span>
          <AssigneePicker
            members={members}
            value={input.assignee === null ? "" : String(input.assignee)}
            onChange={(value) =>
              update("assignee", value ? Number(value) : null)
            }
            disabled={busy}
            loading={membersLoading}
            error={membersError}
            onRetry={onRetryMembers}
          />
          {fieldError("assignee")}
        </div>
        <div className={styles.field}>
          <label htmlFor={`${id}-due`}>Due date</label>
          <input
            id={`${id}-due`}
            type="date"
            value={input.due_date || ""}
            disabled={busy}
            onChange={(event) => update("due_date", event.target.value || null)}
            className={days ? styles.overdue : undefined}
            aria-invalid={Boolean(fields.due_date)}
            aria-describedby={days ? `${id}-overdue` : undefined}
          />
          {fieldError("due_date")}
        </div>
      </div>
      {days > 0 && (
        <p className={styles.overdue} id={`${id}-overdue`}>
          Overdue by {days} {days === 1 ? "day" : "days"}
        </p>
      )}
      {editing && description}
      {metadata}
      <div className={styles.formFooter}>
        {deleteAction}
        <div className={styles.actions}>
          <button
            className={styles.secondaryButton}
            type="button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            className={styles.primaryButton}
            disabled={busy || (editing && !changed)}
          >
            {busy ? "Saving…" : editing ? "Save changes" : "Create task"}
          </button>
        </div>
      </div>
    </form>
  );
}
