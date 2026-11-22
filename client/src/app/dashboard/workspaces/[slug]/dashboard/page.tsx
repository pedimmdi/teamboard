"use client";
import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  getWorkspaceDashboard,
  type WorkspaceDashboard,
  type DashboardItem,
} from "@/lib/workspace-dashboard";
import styles from "./overview.module.css";
const sections = [
  ["my_tasks", "My Tasks", "Your active tasks"],
  ["follow_up", "Follow Up", "Tasks you created for teammates"],
] as const;
export default function WorkspaceDashboardPage() {
  const { ui, formatDate, formatNumber } = useWorkspaceLocale();
  const { slug } = useParams<{
    slug: string;
  }>();
  const { accessToken } = useAuth();
  const [result, setResult] = useState<{
    slug: string;
    data: WorkspaceDashboard;
  } | null>(null);
  const [failure, setFailure] = useState<{
    slug: string;
    message: string;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    getWorkspaceDashboard(accessToken, slug)
      .then((data) => {
        if (!cancelled) {
          setResult({ slug, data });
          setFailure(null);
        }
      })
      .catch(() => {
        if (!cancelled)
          setFailure({
            slug,
            message: "Unable to load this workspace’s dashboard.",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, slug, retry]);
  const data = result?.slug === slug ? result.data : null;
  const error = failure?.slug === slug ? failure.message : null;
  const base = `/dashboard/workspaces/${encodeURIComponent(slug)}`;
  function itemLink(key: string, item: DashboardItem) {
    if (key === "projects") return `${base}/projects/${item.id}/tasks`;
    if (key === "upcoming_events")
      return `${base}/projects/${item.project}/calendar`;
    return `${base}/projects/${item.project}/tasks?task=${encodeURIComponent(item.task ?? item.id)}`;
  }
  return (
    <section className={styles.page} aria-label={ui("Workspace dashboard")}>
      <header className={styles.header}>
        <div>
          <h1>{ui("Dashboard")}</h1>
          <p><bdi>{data?.workspace_name ?? ui("Your workspace")}</bdi></p>
        </div>
      </header>
      {error ? (
        <div role="alert" className={styles.card}>
          <p>{ui(error)}</p>
          <button
            onClick={() => {
              setFailure(null);
              setRetry((v) => v + 1);
            }}
          >{ui("Try again")}</button>
        </div>
      ) : !data ? (
        <p role="status" className={styles.card}>{ui("Loading your dashboard…")}</p>
      ) : (
        <>
          <div className={styles.metrics} aria-label={ui("Task summary")}>
            {([
              ["My tasks today", data.today_tasks_count],
              ["Overdue", data.overdue_tasks.count],
              ["Follow up", data.follow_up.count],
              ["Due in 7 days", data.due_soon_tasks.count],
            ] as const).map(([label, count]) => (
              <div className={styles.metric} key={label}>
                <span>{ui(label)}</span>
                <strong>{formatNumber(count)}</strong>
              </div>
            ))}
          </div>
          <div className={styles.grid}>
            {sections.map(([key, title, description]) => {
              const section = data[key];
              return (
                <article className={styles.card} key={key} aria-label={ui(title)}>
                  <header>
                    <h2>{ui(title)}</h2>
                    <strong className={styles.count}>
                      {formatNumber(section.count)}
                    </strong>
                  </header>
                  <p className={styles.note}>{ui(description)}</p>
                  {section.items.length ? (
                    <ul>
                      {section.items.slice(0, 5).map((item) => (
                        <li key={item.id}>
                          <Link href={itemLink(key, item)}>
                            <bdi>{item.title ?? item.task_title ?? item.name}</bdi>
                          </Link>
                          <small>
                            {[
                              item.project_name,
                              item.due_date ? ui("Due {0}", formatDate(item.due_date, { dateStyle: "medium" })) : null,
                              item.run_at
                                ? formatDate(item.run_at, { dateStyle: "medium", timeStyle: "short" })
                                : null,
                              item.starts_at
                                ? formatDate(item.starts_at, { dateStyle: "medium", timeStyle: "short" })
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </small>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className={styles.empty}>{ui("Nothing here right now.")}</p>
                  )}
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
