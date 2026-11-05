"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getTask,
  updateTask,
  type ProjectMember,
  type Task,
} from "@/lib/api";
import TaskDialog from "./task-dialog";
import TaskForm from "./task-form";
import TaskIcon from "./task-icons";
import { taskChanges, taskInput } from "./task-utils";
import styles from "./tasks.module.css";

export default function TaskDrawer({
  token,
  slug,
  projectId,
  taskId,
  canDelete,
  members,
  membersLoading,
  membersError,
  onRetryMembers,
  onClose,
  onSaved,
  onDelete,
  onMissing,
}: {
  token: string;
  slug: string;
  projectId: string;
  taskId: string;
  canDelete: boolean;
  members: ProjectMember[];
  membersLoading: boolean;
  membersError: string;
  onRetryMembers: () => void;
  onClose: () => void;
  onSaved: () => void;
  onDelete: (task: Task) => void;
  onMissing: () => void;
}) {
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const missing = useRef(onMissing);
  useEffect(() => {
    missing.current = onMissing;
  }, [onMissing]);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getTask(token, slug, projectId, taskId);
        if (!cancelled) setTask(data);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) missing.current();
          else
            setError(
              err instanceof Error ? err.message : "Unable to load task.",
            );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token, slug, projectId, taskId, reload]);
  const deletion =
    task && canDelete ? (
      <button
        type="button"
        className={styles.dangerOutline}
        disabled={busy}
        onClick={() => onDelete(task)}
      >
        Delete task
      </button>
    ) : (
      <p className={styles.hint}>
        Only project managers and workspace admins can delete tasks.
      </p>
    );
  return (
    <TaskDialog
      title="Task"
      drawer
      onClose={onClose}
      busy={busy}
      headerAction={
        task &&
        canDelete && (
          <button
            type="button"
            className={`${styles.iconButton} ${styles.mobileDelete}`}
            aria-label="Delete task"
            disabled={busy}
            onClick={() => onDelete(task)}
          >
            <TaskIcon name="trash" />
          </button>
        )
      }
    >
      {loading ? (
        <p role="status" className={styles.muted}>
          Loading task…
        </p>
      ) : error ? (
        <>
          <p className={styles.alert} role="alert">
            {error}
          </p>
          <button
            className={styles.secondaryButton}
            onClick={() => setReload((value) => value + 1)}
          >
            Try again
          </button>
        </>
      ) : (
        task && (
          <TaskForm
            key={task.updated_at}
            initial={taskInput(task)}
            editing
            members={members}
            membersLoading={membersLoading}
            membersError={membersError}
            onRetryMembers={onRetryMembers}
            onCancel={onClose}
            onBusyChange={setBusy}
            deleteAction={deletion}
            metadata={
              <p className={styles.metadata}>
                Created by {task.created_by_email || "a former member"} ·{" "}
                {new Intl.DateTimeFormat("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                }).format(new Date(task.created_at))}
                <br />
                Updated{" "}
                {new Intl.DateTimeFormat("en-US", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(task.updated_at))}
              </p>
            }
            onSubmit={async (input) => {
              try {
                const saved = await updateTask(
                  token,
                  slug,
                  projectId,
                  task.id,
                  taskChanges(taskInput(task), input),
                );
                setTask(saved);
                onSaved();
              } catch (err) {
                if (err instanceof ApiError && err.status === 404)
                  missing.current();
                throw err;
              }
            }}
          />
        )
      )}
    </TaskDialog>
  );
}
