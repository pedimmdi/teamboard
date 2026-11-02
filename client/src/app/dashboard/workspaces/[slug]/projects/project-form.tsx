"use client";

import { useId, useState, type FormEvent } from "react";
import { ApiError, type ProjectInput } from "@/lib/api";
import styles from "./projects.module.css";

export default function ProjectForm({
  initial = { name: "", description: "" },
  submitLabel,
  onSubmit,
  onCancel,
  onBusyChange,
}: {
  initial?: ProjectInput;
  submitLabel: string;
  onSubmit: (data: ProjectInput) => Promise<void>;
  onCancel?: () => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const id = useId();
  const [name, setName] = useState(initial.name);
  const [description, setDescription] = useState(initial.description);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) {
      setFields({ name: "Project name is required." });
      return;
    }
    setBusy(true);
    onBusyChange?.(true);
    setError("");
    setFields({});
    try {
      await onSubmit({ name: name.trim(), description });
    } catch (err) {
      if (err instanceof ApiError && err.errors) {
        const next: Record<string, string> = {};
        for (const key of ["name", "description"])
          if (err.errors[key])
            next[key] = Array.isArray(err.errors[key])
              ? err.errors[key].join(" ")
              : String(err.errors[key]);
        setFields(next);
        if (!Object.keys(next).length) setError(err.message);
      } else
        setError(
          err instanceof Error ? err.message : "Unable to save project.",
        );
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  }
  return (
    <form className={styles.form} onSubmit={submit}>
      {error && (
        <p className={styles.alert} role="alert">
          {error}
        </p>
      )}
      <div className={styles.field}>
        <label htmlFor={`${id}-name`}>Project name</label>
        <input
          id={`${id}-name`}
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={150}
          disabled={busy}
          aria-invalid={Boolean(fields.name)}
          aria-describedby={fields.name ? `${id}-name-error` : undefined}
          autoComplete="off"
        />
        {fields.name && (
          <p id={`${id}-name-error`} className={styles.error} role="alert">
            {fields.name}
          </p>
        )}
      </div>
      <div className={styles.field}>
        <label htmlFor={`${id}-description`}>
          Description {submitLabel === "Create project" && "(optional)"}
        </label>
        <textarea
          id={`${id}-description`}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={5000}
          disabled={busy}
          placeholder="What is this project about?"
          aria-invalid={Boolean(fields.description)}
          aria-describedby={`${id}-count`}
        />
        <span id={`${id}-count`} className={styles.counter}>
          {description.length} / 5000
        </span>
        {fields.description && (
          <p className={styles.error} role="alert">
            {fields.description}
          </p>
        )}
      </div>
      <div className={styles.actions}>
        {onCancel && (
          <button
            type="button"
            className={styles.secondaryButton}
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
        <button
          className={styles.primaryButton}
          disabled={
            busy ||
            (submitLabel === "Save changes" &&
              name.trim() === initial.name &&
              description === initial.description)
          }
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
