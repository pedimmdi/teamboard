"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createProject, getProjects, type PaginatedProjects } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import DesignIcon from "@/components/ui/DesignIcon";
import { useWorkspace } from "../workspace-context";
import ProjectDialog from "./project-dialog";
import ProjectForm from "./project-form";
import styles from "./projects.module.css";
import { projectRoleLabel, formatProjectDate } from "./project-utils";

export default function ProjectsPage() {
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const [result, setResult] = useState<PaginatedProjects | null>(null);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const canCreate = workspace.role === "owner" || workspace.role === "admin";
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const data = await getProjects(accessToken!, workspace.slug, page);
        if (!cancelled) setResult(data);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Unable to load projects.",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, page, reload]);
  const base = `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/projects`;
  const badge = (role: "manager" | "member" | null) => (
    <span
      className={`${styles.badge} ${role === "manager" ? styles.manager : role === null ? styles.admin : ""}`}
    >
      {projectRoleLabel(role)}
    </span>
  );
  const start = result?.results.length ? (page - 1) * 20 + 1 : 0;
  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <header className={styles.header}>
          <div>
            <h1>Projects</h1>
            <p>
              {canCreate ? "All projects in" : "Projects you’re a member of in"}{" "}
              {workspace.name}.
            </p>
          </div>
          {canCreate && (
            <button
              className={styles.primaryButton}
              onClick={() => setCreating(true)}
            >
              New project
            </button>
          )}
        </header>
        {loading ? (
          <div className={styles.status} role="status">
            Loading projects…
          </div>
        ) : error ? (
          <div className={styles.status}>
            <p role="alert" className={styles.alert}>
              {error}
            </p>
            <button
              className={styles.secondaryButton}
              onClick={() => setReload((value) => value + 1)}
            >
              Try again
            </button>
          </div>
        ) : result?.results.length ? (
          <div className={styles.tableCard}>
            <div className={styles.desktopTable}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>PROJECT</th>
                    <th>YOUR ROLE</th>
                    <th>CREATED</th>
                    <th aria-label="Open project" />
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <Link
                          className={styles.projectLink}
                          href={`${base}/${project.id}/tasks`}
                        >
                          {project.name}
                        </Link>
                        <p className={styles.rowDescription}>
                          {project.description}
                        </p>
                      </td>
                      <td>{badge(project.role)}</td>
                      <td>{formatProjectDate(project.created_at)}</td>
                      <td>
                        <Link
                          href={`${base}/${project.id}/tasks`}
                          aria-label={`Open ${project.name}`}
                        >
                          <DesignIcon name="chevron-right" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={styles.mobileList}>
              {result.results.map((project) => (
                <article className={styles.mobileCard} key={project.id}>
                  <div className={styles.mobileTitle}>
                    <Link
                      className={styles.projectLink}
                      href={`${base}/${project.id}/tasks`}
                    >
                      {project.name}
                    </Link>
                    {badge(project.role)}
                  </div>
                  <p className={styles.rowDescription}>{project.description}</p>
                  <div className={styles.mobileFooter}>
                    <span>Created {formatProjectDate(project.created_at)}</span>
                    <Link
                      href={`${base}/${project.id}/tasks`}
                      aria-label={`Open ${project.name}`}
                    >
                      <DesignIcon name="chevron-right" />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
            <div className={styles.pagination}>
              <span>
                Showing {start}–{start ? start + result.results.length - 1 : 0}{" "}
                of {result.count}
              </span>
              <div className={styles.paginationButtons}>
                <button
                  className={styles.secondaryButton}
                  disabled={!result.previous}
                  onClick={() => setPage((value) => value - 1)}
                >
                  Previous
                </button>
                <button
                  className={styles.secondaryButton}
                  disabled={!result.next}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        ) : (
          <section className={styles.empty}>
            <span className={styles.emptyIcon}>
              <DesignIcon name="folder" />
            </span>
            <h2>
              {canCreate ? "No projects yet" : "You’re not in any project yet"}
            </h2>
            <p className={styles.muted}>
              {canCreate
                ? "Create your first project to start organizing your team’s work."
                : "Ask a project manager or a workspace admin to add you to a project."}
            </p>
          </section>
        )}
        {!canCreate && Boolean(result?.results.length) && (
          <p className={styles.hint}>
            You only see projects you’ve been added to. Ask a workspace admin if
            one is missing.
          </p>
        )}
        {creating && accessToken && (
          <ProjectDialog
            title="New project"
            description={`Projects group a team’s work inside ${workspace.name}. You’ll be its first manager.`}
            busy={saving}
            onClose={() => setCreating(false)}
          >
            <ProjectForm
              submitLabel="Create project"
              onBusyChange={setSaving}
              onCancel={() => setCreating(false)}
              onSubmit={async (data) => {
                await createProject(accessToken, workspace.slug, data);
                setCreating(false);
                setPage(1);
                setReload((value) => value + 1);
              }}
            />
          </ProjectDialog>
        )}
      </div>
    </div>
  );
}
