"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { createProject, getProjects, type PaginatedProjects } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/ui/Avatar";
import TaskIcon from "./[projectId]/tasks/task-icons";
import DesignIcon from "@/components/ui/DesignIcon";
import { useWorkspace } from "../workspace-context";
import ProjectDialog from "./project-dialog";
import ProjectForm from "./project-form";
import styles from "./projects.module.css";
import { projectRoleLabel, formatProjectDate } from "./project-utils";

function subscribeToMobile(callback: () => void) {
  const query = window.matchMedia("(max-width: 767px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export default function ProjectsPage() {
  const { ui, locale, formatNumber } = useWorkspaceLocale();
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const [result, setResult] = useState<PaginatedProjects | null>(null);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const mobile = useSyncExternalStore(subscribeToMobile, () => window.matchMedia("(max-width: 767px)").matches, () => false);
  const [view, setView] = useState<"board" | "list">("board");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const canCreate = workspace.role === "owner" || workspace.role === "admin";
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      setView(localStorage.getItem("teamboard:project-view") === "list" ? "list" : "board");
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
      className={`${styles.badge} ${role === "manager" ? styles.manager : ""}`} data-role-tone={role === "member" ? "member" : role === null ? "admin" : undefined}
    >
      {ui(projectRoleLabel(role))}
    </span>
  );
  const start = result?.results.length ? (page - 1) * 20 + 1 : 0;
  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <header className={styles.header}>
          <div>
            <h1>{ui("Projects")}</h1>
            <p>
              {canCreate ? ui("All projects in") : ui("Projects you’re a member of in")}{" "}
              {workspace.name}.
            </p>
          </div>
          {canCreate && (
            <button
              className={styles.primaryButton}
              onClick={() => setCreating(true)}
            >{ui("New project")}</button>
          )}
        </header>
        <div hidden={mobile} className={mobile ? undefined : styles.projectView} role="group" aria-label={ui("Project view")}>
          {(["board", "list"] as const).map((option) => (
            <button
              type="button"
              key={option}
              aria-pressed={view === option}
              className={styles.secondaryButton}
              onClick={() => {
                setView(option);
                localStorage.setItem("teamboard:project-view", option);
              }}
            >
              <TaskIcon name={option} />
              {option === "board" ? ui("Board") : ui("List")}
            </button>
          ))}
        </div>
        {loading ? (
          <div className={styles.status} role="status">{ui("Loading projects…")}</div>
        ) : error ? (
          <div className={styles.status}>
            <p role="alert" className={styles.alert}>
              {ui(error)}
            </p>
            <button
              className={styles.secondaryButton}
              onClick={() => setReload((value) => value + 1)}
            >{ui("Try again")}</button>
          </div>
        ) : result?.results.length ? (
          <div className={styles.tableCard}>
            {!mobile && view === "board" ? (
              <div className={styles.projectBoard}>
                {result.results.map((project) => (
                  <Link className={styles.projectBoardCard} key={project.id} href={`${base}/${project.id}/tasks`}>
                    <div className={styles.projectIdentity}>
                      <Avatar className={styles.avatar} src={project.avatar} fallback={project.name.charAt(0).toUpperCase()} size={32} />
                      <strong>{project.name}</strong>
                    </div>
                    <p className={styles.rowDescription}>{project.description}</p>
                    <div className={styles.mobileFooter}>
                      {badge(project.role)}
                      <span>{formatProjectDate(project.created_at, locale)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            ) : <>
            <div className={styles.desktopTable}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>{ui("PROJECT")}</th>
                    <th>{ui("YOUR ROLE")}</th>
                    <th>{ui("CREATED")}</th>
                    <th aria-label={ui("Open project")} />
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
                          <Avatar className={styles.avatar} src={project.avatar} fallback={project.name.charAt(0).toUpperCase()} size={32} />
                          {project.name}
                        </Link>
                        <p className={styles.rowDescription}>
                          {project.description}
                        </p>
                      </td>
                      <td>{badge(project.role)}</td>
                      <td>{formatProjectDate(project.created_at, locale)}</td>
                      <td>
                        <Link
                          href={`${base}/${project.id}/tasks`}
                          aria-label={ui("Open {0}", project.name)}
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
                <article className={styles.mobileCard + " " + styles.clickableCard} key={project.id}>
                  <div className={styles.mobileTitle}>
                    <Link
                      className={styles.projectLink}
                      href={`${base}/${project.id}/tasks`}
                    >
                      <Avatar className={styles.avatar} src={project.avatar} fallback={project.name.charAt(0).toUpperCase()} size={32} />
                      {project.name}
                    </Link>
                    {badge(project.role)}
                  </div>
                  <p className={styles.rowDescription}>{project.description}</p>
                  <div className={styles.mobileFooter}>
                    <span>{ui("Created")} {formatProjectDate(project.created_at, locale)}</span>
                    <Link
                      href={`${base}/${project.id}/tasks`}
                      aria-label={ui("Open {0}", project.name)}
                    >
                      <DesignIcon name="chevron-right" />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
            </>}
            <div className={styles.pagination}>
              <span>
                {ui("Showing")} {formatNumber(start)}–{start ? start + result.results.length - 1 : 0}{" "}
                {ui("of")} {result.count}
              </span>
              <div className={styles.paginationButtons}>
                <button
                  className={styles.secondaryButton}
                  disabled={!result.previous}
                  onClick={() => setPage((value) => value - 1)}
                >{ui("Previous")}</button>
                <button
                  className={styles.secondaryButton}
                  disabled={!result.next}
                  onClick={() => setPage((value) => value + 1)}
                >{ui("Next")}</button>
              </div>
            </div>
          </div>
        ) : (
          <section className={styles.empty}>
            <span className={styles.emptyIcon}>
              <DesignIcon name="folder" />
            </span>
            <h2>
              {canCreate ? ui("No projects yet") : ui("You’re not in any project yet")}
            </h2>
            <p className={styles.muted}>
              {canCreate
                ? ui("Create your first project to start organizing your team’s work.")
                : ui("Ask a project manager or a workspace admin to add you to a project.")}
            </p>
          </section>
        )}
        {!canCreate && Boolean(result?.results.length) && (
          <p className={styles.hint}>{ui("You only see projects you’ve been added to. Ask a workspace admin if one is missing.")}</p>
        )}
        {creating && accessToken && (
          <ProjectDialog
            title={ui("New project")}
            description={ui("Projects group a team’s work inside {0}. You’ll be its first manager.", workspace.name)}
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
