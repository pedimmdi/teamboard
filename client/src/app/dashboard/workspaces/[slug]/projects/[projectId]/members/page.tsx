"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  getProjectMembers,
  removeProjectMember,
  updateProjectMemberRole,
  type PaginatedProjectMembers,
  type ProjectMember,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/ui/Avatar";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";
import { formatProjectDate, projectPermissions } from "../../project-utils";
import ProjectDialog from "../../project-dialog";
import AddMemberModal from "./add-member-modal";
import MemberActions from "./member-actions";
import styles from "../../projects.module.css";

type Action = { kind: "role" | "remove"; member: ProjectMember };

export default function ProjectMembersPage() {
  const workspace = useWorkspace();
  const { project, updateProject } = useProjectContext();
  const { accessToken } = useAuth();
  const permissions = projectPermissions(workspace.role, project.role);
  const [result, setResult] = useState<PaginatedProjectMembers | null>(null);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [blocked, setBlocked] = useState(false);
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getProjectMembers(
          accessToken!,
          workspace.slug,
          project.id,
          page,
        );
        if (!cancelled) {
          if (!data.results.length && page > 1) setPage((value) => value - 1);
          else setResult(data);
        }
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load project members.",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, project.id, page, reload]);
  function openAction(kind: Action["kind"], member: ProjectMember) {
    setAction({ kind, member });
    setActionError("");
    setBlocked(false);
  }
  async function confirm() {
    if (!action || !accessToken || busy) return;
    setBusy(true);
    setActionError("");
    try {
      if (action.kind === "role")
        await updateProjectMemberRole(
          accessToken,
          workspace.slug,
          project.id,
          action.member.id,
          action.member.role === "manager" ? "member" : "manager",
        );
      else
        await removeProjectMember(
          accessToken,
          workspace.slug,
          project.id,
          action.member.id,
        );
      if (action.kind === "role" && action.member.is_current_user) {
        updateProject({
          ...project,
          role: action.member.role === "manager" ? "member" : "manager",
        });
      }
      setAction(null);
      setReload((value) => value + 1);
    } catch (err) {
      const fields = err instanceof ApiError ? err.errors : null;
      const message = fields
        ? [fields.role, fields.detail].filter(Boolean).flat().join(" ")
        : "";
      const text =
        message ||
        (err instanceof Error ? err.message : "Unable to update member.");
      setActionError(text);
      if (
        err instanceof ApiError &&
        [400, 409].includes(err.status) &&
        /manager/i.test(text)
      )
        setBlocked(true);
    } finally {
      setBusy(false);
    }
  }
  const actions = (member: ProjectMember) => (
    <MemberActions
      member={member}
      canAssignManagers={permissions.canAssignManagers}
      canManage={permissions.canManage}
      onRole={() => openAction("role", member)}
      onRemove={() => openAction("remove", member)}
    />
  );
  const identity = (member: ProjectMember) => (
    <div className={styles.memberIdentity}>
      <Avatar
        className={styles.avatar}
        src={member.avatar}
        fallback={member.user_email.charAt(0).toUpperCase()}
        size={32}
      />
      <span className={styles.email}>
        {member.user_email}
        {member.is_current_user && <small className={styles.you}>You</small>}
      </span>
    </div>
  );
  return (
    <div className={styles.overview}>
      <header className={styles.sectionHeader}>
        <div>
          <h2>Members</h2>
          <p className={styles.muted}>People who can work on this project.</p>
        </div>
        {permissions.canManage && (
          <button
            className={styles.primaryButton}
            onClick={() => setAdding(true)}
          >
            Add member
          </button>
        )}
      </header>
      {loading ? (
        <div className={styles.status} role="status">
          Loading members…
        </div>
      ) : error ? (
        <div className={styles.status}>
          <p className={styles.alert} role="alert">
            {error}
          </p>
          <button
            className={styles.secondaryButton}
            onClick={() => setReload((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      ) : (
        <div className={styles.tableCard}>
          <div className={styles.desktopTable}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>MEMBER</th>
                  <th>ROLE</th>
                  <th>JOINED</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {result?.results.map((member) => (
                  <tr key={member.id}>
                    <td>{identity(member)}</td>
                    <td>
                      <span
                        className={`${styles.badge} ${member.role === "manager" ? styles.manager : ""}`}
                      >
                        {member.role === "manager" ? "Manager" : "Member"}
                      </span>
                    </td>
                    <td>{formatProjectDate(member.joined_at)}</td>
                    <td>{actions(member)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={styles.mobileList}>
            {result?.results.map((member) => (
              <article className={styles.mobileCard} key={member.id}>
                <div className={styles.mobileTitle}>
                  {identity(member)}
                  {actions(member)}
                </div>
                <div className={styles.memberMeta}>
                  <span
                    className={`${styles.badge} ${member.role === "manager" ? styles.manager : ""}`}
                  >
                    {member.role === "manager" ? "Manager" : "Member"}
                  </span>
                  <small>Joined {formatProjectDate(member.joined_at)}</small>
                </div>
              </article>
            ))}
          </div>
          <div className={styles.pagination}>
            <span>
              Showing {result?.results.length ? (page - 1) * 20 + 1 : 0}–
              {result?.results.length
                ? (page - 1) * 20 + result.results.length
                : 0}{" "}
              of {result?.count ?? 0}
            </span>
            <div className={styles.paginationButtons}>
              <button
                className={styles.secondaryButton}
                disabled={!result?.previous}
                onClick={() => setPage((value) => value - 1)}
              >
                Previous
              </button>
              <button
                className={styles.secondaryButton}
                disabled={!result?.next}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
      {adding && accessToken && (
        <AddMemberModal
          token={accessToken}
          slug={workspace.slug}
          workspaceName={workspace.name}
          projectId={project.id}
          projectName={project.name}
          canAssignManagers={permissions.canAssignManagers}
          onClose={() => setAdding(false)}
          onAdded={() => {
            setAdding(false);
            setReload((value) => value + 1);
          }}
        />
      )}
      {action && (
        <ProjectDialog
          title={
            blocked
              ? action.kind === "role"
                ? "Can’t change this role"
                : "Can’t remove this member"
              : action.kind === "role"
                ? `Make ${action.member.role === "manager" ? "member" : "manager"}?`
                : `Remove ${action.member.user_email}?`
          }
          description={
            action.kind === "remove"
              ? `They’ll lose access to ${project.name} right away. They’ll stay in the workspace.`
              : `Update the project role for ${action.member.user_email}.`
          }
          busy={busy}
          onClose={() => setAction(null)}
        >
          {actionError && (
            <p className={styles.alert} role="alert">
              {actionError}
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
            {!blocked && (
              <button
                className={
                  action.kind === "remove"
                    ? styles.dangerButton
                    : styles.primaryButton
                }
                disabled={busy}
                onClick={() => void confirm()}
              >
                {busy
                  ? "Saving…"
                  : action.kind === "remove"
                    ? "Remove member"
                    : "Change role"}
              </button>
            )}
          </div>
        </ProjectDialog>
      )}
    </div>
  );
}
