"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
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
  const { ui, locale } = useWorkspaceLocale();
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
        <nav aria-label={ui("Breadcrumb")} className={styles.breadcrumb}>
          <Link href={projectsPath}>{ui("← Projects")}</Link>
          {project && (
            <span className={styles.breadcrumbName}><span aria-hidden="true">{locale === "fa" ? "‹" : "›"}</span> <bdi>{project.name}</bdi></span>
          )}
        </nav>
        {loading ? (
          <div className={styles.status} role="status">{ui("Loading project…")}</div>
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
        ) : project && project.id === projectId ? (
          <>
            <header className={`${styles.header} ${styles.projectHeader}`}>
              <div className={styles.titleRow}>
                <Avatar className={styles.avatar} src={project.avatar} fallback={project.name.charAt(0).toUpperCase()} size={32} />
                <h1><bdi>{project.name}</bdi></h1>
                <span
                  className={`${styles.badge} ${project.role === "manager" ? styles.manager : ""}`} data-role-tone={project.role === "member" ? "member" : project.role === null ? "admin" : undefined}
                >
                  {ui(projectRoleLabel(project.role))}
                </span>
              </div>
            </header>
            {project.description && !isTasks && (
              <p className={styles.projectDescription} dir="auto">{project.description}</p>
            )}
            <nav className={styles.tabs} aria-label={ui("Project navigation")}>
              {[
                { title: ui("Tasks"), href: `${base}/tasks` },
                { title: ui("Calendar"), href: `${base}/calendar` },
                { title: ui("Chat"), href: `${base}/chat` },
                { title: ui("Reports"), href: `${base}/reports` },
                { title: ui("Members"), href: `${base}/members` },
                ...(permissions.canManage || permissions.canLeave
                  ? [{ title: ui("Settings"), href: `${base}/settings` }]
                  : []),
              ].map((tab) => (
                <Link
                  href={tab.href}
                  key={tab.href}
                  aria-current={pathname === tab.href ? "page" : undefined}
                  className={pathname === tab.href ? styles.activeTab : ""}
                >
                  {ui(tab.title)}
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
