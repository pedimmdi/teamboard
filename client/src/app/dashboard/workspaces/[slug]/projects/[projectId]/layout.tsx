"use client";

import Avatar from "@/components/ui/Avatar";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, getProject, type Project } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useWorkspace } from "../../workspace-context";
import { projectPermissions, projectRoleLabel } from "../project-utils";
import { ProjectProvider } from "./project-context";
import styles from "../projects.module.css";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const pathname = usePathname();
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
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
        const result = await getProject(
          accessToken!,
          workspace.slug,
          projectId,
        );
        if (!cancelled) setProject(result);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof ApiError && err.status === 404
              ? "Project not found or access denied."
              : err instanceof Error
                ? err.message
                : "Unable to load project.",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, projectId, reload]);
  const projectsPath = `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/projects`;
  const base = `${projectsPath}/${encodeURIComponent(projectId)}`;
  const isTasks = pathname === `${base}/tasks`;
  const permissions = projectPermissions(workspace.role, project?.role ?? null);
  return (
    <div className={styles.page}>
      <div className={`${styles.content} ${isTasks ? styles.taskContent : ""}`}>
        <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
          <Link href={projectsPath}>← Projects</Link>
          {project && (
            <span className={styles.breadcrumbName}>› {project.name}</span>
          )}
        </nav>
        {loading ? (
          <div className={styles.status} role="status">
            Loading project…
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
        ) : project && project.id === projectId ? (
          <>
            <header className={styles.header}>
              <div className={styles.titleRow}>
                <Avatar className={styles.avatar} src={project.avatar} fallback={project.name.charAt(0).toUpperCase()} size={32} />
                <h1>{project.name}</h1>
                <span
                  className={`${styles.badge} ${project.role === "manager" ? styles.manager : project.role === null ? styles.admin : ""}`}
                >
                  {projectRoleLabel(project.role)}
                </span>
              </div>
            </header>
            {project.description && !isTasks && (
              <p className={styles.projectDescription}>{project.description}</p>
            )}
            <nav className={styles.tabs} aria-label="Project navigation">
              {[
                { title: "Tasks", href: `${base}/tasks` },
                { title: "Members", href: `${base}/members` },
                ...(permissions.canManage || permissions.canLeave
                  ? [{ title: "Settings", href: `${base}/settings` }]
                  : []),
              ].map((tab) => (
                <Link
                  href={tab.href}
                  key={tab.href}
                  aria-current={pathname === tab.href ? "page" : undefined}
                  className={pathname === tab.href ? styles.activeTab : ""}
                >
                  {tab.title}
                </Link>
              ))}
            </nav>
            <ProjectProvider project={project} updateProject={setProject}>
              <div key={project.id}>{children}</div>
            </ProjectProvider>
          </>
        ) : null}
      </div>
    </div>
  );
}
