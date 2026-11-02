"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  addProjectMember,
  ApiError,
  getProjectMembers,
  getWorkspaceMembers,
  type WorkspaceMember,
  type ProjectRole,
} from "@/lib/api";
import ProjectDialog from "../../project-dialog";
import styles from "../../projects.module.css";

export default function AddMemberModal({
  token,
  slug,
  workspaceName,
  projectId,
  projectName,
  canAssignManagers,
  onClose,
  onAdded,
}: {
  token: string;
  slug: string;
  workspaceName: string;
  projectId: string;
  projectName: string;
  canAssignManagers: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const id = useId();
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<ProjectRole>("member");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const existing = new Set<number>();
        for (let page = 1; ; page++) {
          const data = await getProjectMembers(token, slug, projectId, page);
          if (cancelled) return;
          data.results.forEach((member) => existing.add(member.user_id));
          if (!data.next) break;
        }
        const available: WorkspaceMember[] = [];
        for (let page = 1; ; page++) {
          const data = await getWorkspaceMembers(token, slug, page);
          if (cancelled) return;
          available.push(
            ...data.results.filter((member) => !existing.has(member.user_id)),
          );
          if (!data.next) break;
        }
        setMembers(available);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load workspace members.",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token, slug, projectId, reload]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !userId) return;
    setBusy(true);
    setError("");
    try {
      await addProjectMember(token, slug, projectId, Number(userId), role);
      onAdded();
    } catch (err) {
      const fields = err instanceof ApiError ? err.errors : null;
      const messages = fields
        ? [fields.user, fields.user_id, fields.role, fields.detail]
            .filter(Boolean)
            .flat()
            .join(" ")
        : "";
      setError(
        messages ||
          (err instanceof Error ? err.message : "Unable to add member."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <ProjectDialog
      title="Add a member"
      description={`Choose someone from ${workspaceName} to give access to ${projectName}.`}
      busy={busy}
      onClose={onClose}
    >
      {loading ? (
        <p role="status" className={styles.muted}>
          Loading workspace members…
        </p>
      ) : (
        <form className={styles.form} onSubmit={submit}>
          {error && (
            <p className={styles.alert} role="alert">
              {error}
            </p>
          )}
          {!members.length ? (
            <>
              <p className={styles.muted}>
                No available workspace members. Everyone is already in this
                project, or workspace members could not be loaded.
              </p>
              <Link
                href={`/dashboard/workspaces/${encodeURIComponent(slug)}/members`}
                className={styles.secondaryButton}
              >
                View workspace people
              </Link>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => setReload((value) => value + 1)}
              >
                Reload members
              </button>
            </>
          ) : (
            <>
              <div className={styles.field}>
                <label htmlFor={`${id}-member`}>Workspace member</label>
                <select
                  id={`${id}-member`}
                  value={userId}
                  disabled={busy}
                  onChange={(event) => setUserId(event.target.value)}
                  required
                >
                  <option value="">Select a workspace member</option>
                  {members.map((member) => (
                    <option key={member.id} value={member.user_id}>
                      {member.user_email}
                    </option>
                  ))}
                </select>
              </div>
              <fieldset className={styles.roles} disabled={busy}>
                <legend>Role</legend>
                {(["member", "manager"] as const).map((value) => (
                  <label
                    key={value}
                    className={`${styles.radioOption} ${role === value ? styles.selectedRadio : ""}`}
                  >
                    <input
                      type="radio"
                      name={`${id}-role`}
                      value={value}
                      checked={role === value}
                      disabled={value === "manager" && !canAssignManagers}
                      onChange={() => setRole(value)}
                    />
                    <span>
                      <strong>
                        {value === "manager" ? "Manager" : "Member"}
                      </strong>
                      <small>
                        {value === "manager"
                          ? "Can manage details and members. Only workspace owners and admins can assign this role."
                          : "Can view the project and its members."}
                      </small>
                    </span>
                  </label>
                ))}
              </fieldset>
            </>
          )}
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.secondaryButton}
              disabled={busy}
              onClick={onClose}
            >
              Cancel
            </button>
            {members.length > 0 && (
              <button
                className={styles.primaryButton}
                disabled={busy || !userId}
              >
                {busy ? "Adding…" : "Add member"}
              </button>
            )}
          </div>
        </form>
      )}
    </ProjectDialog>
  );
}
