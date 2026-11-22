"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  getTask,
  updateTask,
  type ProjectMember,
  type Task,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import TaskReminders from "./task-reminders";
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
  onCommentCountChange,
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
  onCommentCountChange: (id: string, count: number) => void;
}) {
  const { ui, formatDate, formatNumber } = useWorkspaceLocale();
  const { user } = useAuth();
  const [task, setTask] = useState<Task | null>(null);
  const [section, setSection] = useState<"comments" | "reminders" | "details">("comments");
  const [commentCount, setCommentCount] = useState<number | null>(null);
  const updateCommentCount = useCallback((count: number) => {
    setCommentCount(count);
    onCommentCountChange(taskId, count);
  }, [onCommentCountChange, taskId]);
  const [commentBusy, setCommentBusy] = useState(false);
  const [reminderBusy, setReminderBusy] = useState(false);
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
        disabled={busy || commentBusy || reminderBusy}
        onClick={() => onDelete(task)}
      >{ui("Delete task")}</button>
    ) : (
      <p className={styles.hint}>{ui("Only project managers and workspace admins can delete tasks.")}</p>
    );
  return (
    <TaskDialog
      title={ui("Task")}
      drawer
      onClose={onClose}
      busy={busy || commentBusy || reminderBusy}
      headerAction={
        task &&
        canDelete && (
          <button
            type="button"
            className={`${styles.iconButton} ${styles.mobileDelete}`}
            aria-label={ui("Delete task")}
            disabled={busy || commentBusy || reminderBusy}
            onClick={() => onDelete(task)}
          >
            <TaskIcon name="trash" />
          </button>
        )
      }
    >
      {loading ? (
        <p role="status" className={styles.muted}>{ui("Loading task…")}</p>
      ) : error ? (
        <>
          <p className={styles.alert} role="alert">
            {ui(error)}
          </p>
          <button
            className={styles.secondaryButton}
            onClick={() => setReload((value) => value + 1)}
          >{ui("Try again")}</button>
        </>
      ) : (
        task && (
          <>
            <div className={commentStyles.taskHeading}>
              <h3>{task.title}</h3>
              <div className={commentStyles.taskLabels}>
                <span className={`${styles.badge} ${styles[task.status]}`}>
                  {ui(taskStatuses.find((status) => status.value === task.status)?.label ?? "")}
                </span>
                <span className={`${styles.priority} ${styles[task.priority]}`}>
                  <span className={styles.dot} />
                  {ui(task.priority.charAt(0).toUpperCase() + task.priority.slice(1))}
                </span>
              </div>
            </div>
            <div className={commentStyles.tabs} role="group" aria-label={ui("Task sections")}>
              <button type="button" aria-pressed={section === "comments"} disabled={busy || commentBusy || reminderBusy} onClick={() => setSection("comments")}>
                {ui("Comments")}{commentCount !== null && ` (${formatNumber(commentCount)})`}
              </button>
              <button type="button" aria-pressed={section === "reminders"} disabled={busy || commentBusy || reminderBusy} onClick={() => setSection("reminders")}>{ui("Reminders")}</button>
              <button type="button" aria-pressed={section === "details"} disabled={busy || commentBusy || reminderBusy} onClick={() => setSection("details")}>{ui("Details")}</button>
            </div>
            <div hidden={section !== "details"} inert={reminderBusy}>
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
                      {ui("Created by")} <bdi>{task.created_by_email || ui("a former member")}</bdi> ·{" "}
                      {formatDate(task.created_at, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                      <br />
                      {ui("Updated")}{" "}
                      {formatDate(task.updated_at, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
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
                active={section === "comments"}
                onCountChange={updateCommentCount}
                onBusyChange={setCommentBusy}
              />
            )}
            <div hidden={section !== "reminders"} inert={busy || commentBusy}>
              <TaskReminders key={task.updated_at} token={token} slug={slug} projectId={projectId} task={task} onBusyChange={setReminderBusy} />
            </div>
          </>
        )
      )}
    </TaskDialog>
  );
}
