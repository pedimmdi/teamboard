"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getTask,
  updateTask,
  type ProjectMember,
  type Task,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import TaskComments from "./task-comments";
import TaskDialog from "./task-dialog";
import TaskForm from "./task-form";
import TaskIcon from "./task-icons";
import { taskChanges, taskInput, taskStatuses } from "./task-utils";
import commentStyles from "./task-comments.module.css";
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
  const { user } = useAuth();
  const [task, setTask] = useState<Task | null>(null);
  const [showComments, setShowComments] = useState(false);
  const [commentCount, setCommentCount] = useState<number | null>(null);
  const [commentBusy, setCommentBusy] = useState(false);
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
      busy={busy || commentBusy}
      headerAction={
        task &&
        canDelete && (
          <button
            type="button"
            className={`${styles.iconButton} ${styles.mobileDelete}`}
            aria-label="Delete task"
            disabled={busy || commentBusy}
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
          <>
            <div className={commentStyles.taskHeading}>
              <h3>{task.title}</h3>
              <div className={commentStyles.taskLabels}>
                <span className={`${styles.badge} ${styles[task.status]}`}>
                  {taskStatuses.find((status) => status.value === task.status)?.label}
                </span>
                <span className={`${styles.priority} ${styles[task.priority]}`}>
                  <span className={styles.dot} />
                  {task.priority.charAt(0).toUpperCase() + task.priority.slice(1)}
                </span>
              </div>
            </div>
            <div className={commentStyles.tabs} role="group" aria-label="Task sections">
              <button type="button" aria-pressed={!showComments} disabled={busy || commentBusy} onClick={() => setShowComments(false)}>
                Details
              </button>
              <button type="button" aria-pressed={showComments} disabled={busy || commentBusy} onClick={() => setShowComments(true)}>
                Comments{commentCount !== null && ` (${commentCount})`}
              </button>
            </div>
            <div hidden={showComments}>
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
            </div>
            {user && (
              <TaskComments
                token={token}
                slug={slug}
                projectId={projectId}
                taskId={task.id}
                user={user}
                members={members}
                canModerate={canDelete}
                active={showComments}
                onCountChange={setCommentCount}
                onBusyChange={setCommentBusy}
              />
            )}
          </>
        )
      )}
    </TaskDialog>
  );
}
