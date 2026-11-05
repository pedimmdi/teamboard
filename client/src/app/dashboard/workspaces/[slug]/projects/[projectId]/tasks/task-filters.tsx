"use client";

import { useState } from "react";
import type { ProjectMember } from "@/lib/api";
import AssigneePicker from "./assignee-picker";
import TaskDialog from "./task-dialog";
import {
  emptyTaskFilters,
  taskOrderings,
  taskPriorities,
  taskStatuses,
  type TaskFilters,
} from "./task-utils";
import styles from "./tasks.module.css";

export const orderingLabels: Record<(typeof taskOrderings)[number], string> = {
  due_date: "Due date — soonest first",
  "-due_date": "Due date — latest first",
  "-created_at": "Newest first",
  created_at: "Oldest first",
  "-updated_at": "Recently updated",
  title: "Title — A to Z",
  "-title": "Title — Z to A",
  priority: "Priority — low to urgent",
  "-priority": "Priority — urgent to low",
  status: "Status — To Do to Done",
  "-status": "Status — Done to To Do",
};
export default function TaskFiltersDialog({
  filters,
  view,
  members,
  membersLoading,
  membersError,
  onRetryMembers,
  onApply,
  onClose,
}: {
  filters: TaskFilters;
  view: "board" | "list";
  members: ProjectMember[];
  membersLoading: boolean;
  membersError: string;
  onRetryMembers: () => void;
  onApply: (filters: TaskFilters, view: "board" | "list") => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(filters);
  const [mode, setMode] = useState(view);
  return (
    <TaskDialog title="Filters" onClose={onClose}>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          onApply(draft, mode);
        }}
      >
        <fieldset className={styles.filterGroup}>
          <legend>View</legend>
          <div className={styles.pills}>
            {(["board", "list"] as const).map((value) => (
              <button
                type="button"
                key={value}
                className={mode === value ? styles.selectedPill : styles.pill}
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
              >
                {value === "board" ? "Board" : "List"}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className={styles.filterGroup}>
          <legend>Status</legend>
          <div className={styles.pills}>
            {taskStatuses.map((status) => (
              <button
                type="button"
                key={status.value}
                className={
                  draft.statuses.includes(status.value)
                    ? styles.selectedPill
                    : styles.pill
                }
                aria-pressed={draft.statuses.includes(status.value)}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    statuses: current.statuses.includes(status.value)
                      ? current.statuses.filter(
                          (value) => value !== status.value,
                        )
                      : [...current.statuses, status.value],
                  }))
                }
              >
                {status.label}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className={styles.filterGroup}>
          <legend>Priority</legend>
          <div className={styles.pills}>
            {taskPriorities.map((priority) => (
              <button
                type="button"
                key={priority}
                className={
                  draft.priority === priority
                    ? styles.selectedPill
                    : styles.pill
                }
                aria-pressed={draft.priority === priority}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    priority: current.priority === priority ? "" : priority,
                  }))
                }
              >
                {priority.charAt(0).toUpperCase() + priority.slice(1)}
              </button>
            ))}
          </div>
        </fieldset>
        <div className={styles.field}>
          <span className={styles.fieldLabel}>Assignee</span>
          <AssigneePicker
            filter
            members={members}
            value={draft.assignee}
            onChange={(assignee) =>
              setDraft((current) => ({ ...current, assignee }))
            }
            loading={membersLoading}
            error={membersError}
            onRetry={onRetryMembers}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="task-due-before">Due before</label>
          <input
            id="task-due-before"
            type="date"
            value={draft.dueBefore}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                dueBefore: event.target.value,
              }))
            }
          />
        </div>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={draft.overdue}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                overdue: event.target.checked,
              }))
            }
          />
          Only overdue tasks
        </label>
        <div className={styles.field}>
          <label htmlFor="task-ordering">Sort by</label>
          <select
            id="task-ordering"
            disabled={mode === "board"}
            value={draft.ordering}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                ordering: event.target.value as TaskFilters["ordering"],
              }))
            }
          >
            {taskOrderings.map((ordering) => (
              <option key={ordering} value={ordering}>
                {orderingLabels[ordering]}
              </option>
            ))}
          </select>
          {mode === "board" && (
            <p className={styles.hint}>
              Board cards use their manual order. Drag a card or use Move task
              to change it.
            </p>
          )}
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() =>
              setDraft({ ...emptyTaskFilters, search: draft.search })
            }
          >
            Clear all
          </button>
          <button className={styles.primaryButton}>Apply filters</button>
        </div>
      </form>
    </TaskDialog>
  );
}
