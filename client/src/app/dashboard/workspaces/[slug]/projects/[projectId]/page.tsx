"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getProjectMembers, type ProjectMember } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/ui/Avatar";
import { useWorkspace } from "../../workspace-context";
import { useProjectContext } from "./project-context";
import styles from "../projects.module.css";

export default function ProjectOverviewPage() {
  const { project } = useProjectContext();
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const all: ProjectMember[] = [];
        for (let page = 1; ; page++) {
          const data = await getProjectMembers(
            accessToken!,
            workspace.slug,
            project.id,
            page,
          );
          if (cancelled) return;
          all.push(...data.results);
          if (!data.next) break;
        }
        setMembers(all);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Unable to load team.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, project.id, reload]);
  return (
    <div className={styles.overview}>
      <div className={styles.overviewGrid}>
        <section className={styles.card}>
          <h2>About</h2>
          <p className={styles.aboutText}>
            {project.description || "No description has been added yet."}
          </p>
        </section>
        <section className={styles.card}>
          <h2>Team</h2>
          {loading ? (
            <p className={styles.muted} role="status">
              Loading team…
            </p>
          ) : error ? (
            <>
              <p className={styles.error} role="alert">
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
            <>
              <div className={styles.avatars}>
                {members.slice(0, 5).map((member) => (
                  <span key={member.id} title={member.user_email}>
                    <Avatar
                      className={styles.avatar}
                      src={member.avatar}
                      fallback={member.user_email.charAt(0).toUpperCase()}
                      size={32}
                    />
                  </span>
                ))}
              </div>
              <p className={styles.hint}>
                {members.length} {members.length === 1 ? "member" : "members"} ·{" "}
                {members.filter((member) => member.role === "manager").length}{" "}
                {members.filter((member) => member.role === "manager")
                  .length === 1
                  ? "manager"
                  : "managers"}
              </p>
            </>
          )}
        </section>
      </div>
      <section className={styles.tasksPlaceholder}>
        <span className={styles.emptyIcon} aria-hidden="true">
          ☷
        </span>
        <h2>Tasks</h2>
        <p className={styles.hint}>
          Plan, assign, and track work on this project’s task board.
        </p>
        <Link
          className={styles.primaryButton}
          href={`/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/projects/${project.id}/tasks`}
        >
          View tasks
        </Link>
      </section>
    </div>
  );
}
