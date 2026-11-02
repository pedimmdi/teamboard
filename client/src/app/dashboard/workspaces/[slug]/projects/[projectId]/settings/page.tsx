"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ApiError,
  deleteProject,
  leaveProject,
  updateProject,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";
import { projectPermissions } from "../../project-utils";
import ProjectForm from "../../project-form";
import ProjectDialog from "../../project-dialog";
import styles from "../../projects.module.css";

export default function ProjectSettingsPage() {
  const { project, updateProject: updateContext } = useProjectContext();
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const router = useRouter();
  const permissions = projectPermissions(workspace.role, project.role);
  const [success, setSuccess] = useState("");
  const [action, setAction] = useState<"leave" | "delete" | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const base = `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/projects`;
  function open(kind: "leave" | "delete") {
    setAction(kind);
    setError("");
    setBlocked(false);
    setConfirmation("");
  }
  async function confirm() {
    if (
      !accessToken ||
      !action ||
      busy ||
      (action === "delete" && confirmation !== project.name)
    )
      return;
    setBusy(true);
    setError("");
    try {
      if (action === "delete")
        await deleteProject(accessToken, workspace.slug, project.id);
      else await leaveProject(accessToken, workspace.slug, project.id);
      router.replace(base);
    } catch (err) {
      const text =
        err instanceof Error ? err.message : "Unable to complete this action.";
      setError(text);
      if (
        action === "leave" &&
        err instanceof ApiError &&
        [400, 409].includes(err.status) &&
        /manager/i.test(text)
      )
        setBlocked(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={styles.overview}>
      {permissions.canManage ? (
        <section className={styles.card}>
          <h2>Project details</h2>
          {success && (
            <p className={styles.success} role="status">
              {success}
            </p>
          )}
          <ProjectForm
            key={project.updated_at}
            initial={{ name: project.name, description: project.description }}
            submitLabel="Save changes"
            onSubmit={async (data) => {
              if (!accessToken) return;
              setSuccess("");
              const updated = await updateProject(
                accessToken,
                workspace.slug,
                project.id,
                data,
              );
              updateContext(updated);
              setSuccess("Project details saved.");
            }}
          />
        </section>
      ) : (
        <section className={styles.card}>
          <h2>Project details</h2>
          <p className={styles.muted}>
            Only project managers and workspace admins can edit project details.
          </p>
        </section>
      )}
      {permissions.canLeave && (
        <section className={`${styles.card} ${styles.dangerRow}`}>
          <div>
            <h2>Leave project</h2>
            <p className={styles.hint}>
              {permissions.canDelete
                ? "Leave your personal project membership. Your workspace admin access will remain."
                : "You’ll lose access to this project. The last manager can’t leave."}
            </p>
          </div>
          <button
            className={styles.dangerOutline}
            onClick={() => open("leave")}
          >
            Leave project
          </button>
        </section>
      )}
      {permissions.canDelete && (
        <section
          className={`${styles.card} ${styles.dangerRow} ${styles.dangerCard}`}
        >
          <div>
            <h2>
              Delete project{" "}
              <span className={styles.badge}>Workspace admins only</span>
            </h2>
            <p className={styles.hint}>
              Permanently delete this project and its memberships. This can’t be
              undone.
            </p>
          </div>
          <button
            className={styles.dangerButton}
            onClick={() => open("delete")}
          >
            Delete project
          </button>
        </section>
      )}
      {action && (
        <ProjectDialog
          title={
            blocked
              ? "Can’t leave this project"
              : `${action === "delete" ? "Delete" : "Leave"} ${project.name}?`
          }
          description={
            action === "delete"
              ? "This permanently deletes the project and its memberships. This can’t be undone."
              : permissions.canDelete
                ? "This removes your personal membership. You’ll still have workspace admin access."
                : "You’ll lose access to this project. A manager or workspace admin can add you again."
          }
          busy={busy}
          onClose={() => setAction(null)}
        >
          {action === "delete" && (
            <div className={styles.field}>
              <label htmlFor="confirm-project-name">
                Type the project name to confirm
              </label>
              <input
                id="confirm-project-name"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder={project.name}
                autoComplete="off"
                disabled={busy}
              />
            </div>
          )}
          {error && (
            <p className={styles.alert} role="alert">
              {error}
            </p>
          )}
          <div className={styles.actions}>
            <button
              className={styles.secondaryButton}
              disabled={busy}
              onClick={() => setAction(null)}
            >
              {blocked ? "Close" : "Cancel"}
            </button>
            {blocked ? (
              <Link
                className={styles.primaryButton}
                href={`${base}/${project.id}/members`}
              >
                Manage members
              </Link>
            ) : (
              <button
                className={styles.dangerButton}
                disabled={
                  busy || (action === "delete" && confirmation !== project.name)
                }
                onClick={() => void confirm()}
              >
                {busy
                  ? "Working…"
                  : action === "delete"
                    ? "Delete project"
                    : "Leave project"}
              </button>
            )}
          </div>
        </ProjectDialog>
      )}
    </div>
  );
}
