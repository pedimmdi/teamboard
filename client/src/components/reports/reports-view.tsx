"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError, exportReport, getReportHistory, getReportOverview, getReportRanking,
  getReportWorkload, getWorkspaceMembers, type ReportFilters, type ReportHistory, type ReportOverview,
  type ReportRanking, type ReportWorkload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { reportDateRange, validateReportDates } from "./report-utils";
import ReportIcon from "./report-icon";
import styles from "./reports.module.css";

type ReportData = { overview: ReportOverview; history: ReportHistory; workload: ReportWorkload[]; ranking?: ReportRanking };
const labels: Record<string, string> = { todo: "To do", in_progress: "In progress", in_review: "In review", done: "Done", low: "Low", medium: "Medium", high: "High", urgent: "Urgent" };
function errorMessage(error: unknown) {
  return (error instanceof ApiError && error.errors ? Object.values(error.errors).flat().join(" ") : "")
    || (error instanceof Error ? error.message : "Unable to load reports.");
}

export default function ReportsView({ slug, projectId, workspaceRole }: { slug: string; projectId?: string; workspaceRole: string | null }) {
  const { ui, formatDate, formatNumber } = useWorkspaceLocale();
  const { accessToken } = useAuth();
  const [members, setMembers] = useState<{ slug: string; rows: { user_id: number; user_email: string }[] }>();
  const [memberError, setMemberError] = useState(false);
  const [memberRevision, setMemberRevision] = useState(0);
  const [filters, setFilters] = useState<ReportFilters>(() => reportDateRange(30));
  const [granularity, setGranularity] = useState("day");
  const [ordering, setOrdering] = useState("-completed_tasks");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; data?: ReportData; error?: string }>();
  const [formError, setFormError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const key = JSON.stringify([slug, projectId, filters, granularity, page, ordering, revision]);
  const current = result?.key === key ? result : undefined;
  const data = current?.data;

  useEffect(() => {
    if (!accessToken) return;
    const controller = new AbortController();
    Promise.all([
      getReportOverview(accessToken, slug, projectId, controller.signal),
      getReportHistory(accessToken, slug, { ...filters, granularity }, projectId, controller.signal),
      getReportWorkload(accessToken, slug, filters, projectId, controller.signal),
      projectId ? Promise.resolve(undefined) : getReportRanking(accessToken, slug, filters, page, ordering, controller.signal),
    ]).then(([overview, history, workload, ranking]) => {
      if (!controller.signal.aborted) setResult({ key, data: { overview, history, workload, ranking } });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setResult({ key, error: errorMessage(error) });
    });
    return () => controller.abort();
  }, [accessToken, slug, projectId, filters, granularity, page, ordering, key]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function loadMembers() {
      const rows = [];
      for (let page = 1; !cancelled; page++) {
        const response = await getWorkspaceMembers(accessToken!, slug, page);
        rows.push(...response.results);
        if (!response.next) break;
      }
      if (!cancelled) { setMembers({ slug, rows }); setMemberError(false); }
    }
    void loadMembers().catch(() => { if (!cancelled) setMemberError(true); });
    return () => { cancelled = true; };
  }, [accessToken, slug, memberRevision]);

  const memberOptions = members?.slug === slug ? members.rows : data?.overview.member_workload ?? [];

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const start = String(fields.get("start"));
    const end = String(fields.get("end"));
    if (!validateReportDates(start, end)) {
      setFormError("Choose an ordered date range of at most 366 days.");
      return;
    }
    setFormError("");
    setExportError("");
    setPage(1);
    setFilters({ start_date: start, end_date: end, assignee: String(fields.get("assignee")),
      status: String(fields.get("status")), priority: String(fields.get("priority")) });
  }

  async function download() {
    if (!accessToken || exporting) return;
    setExporting(true);
    setExportError("");
    try {
      const blob = await exportReport(accessToken, slug, filters, projectId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "task-report.csv";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setExportError(errorMessage(error));
    } finally {
      setExporting(false);
    }
  }

  const totals = (rows: ReportHistory["results"], field: "created" | "completed") => rows.reduce((sum, row) => sum + row[field], 0);
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null);
  const activeBucket = data?.history.results.find((row) => row.date === selectedBucket);
  const formatDay = (day: string) => new Intl.DateTimeFormat("en", {
    month: "short", day: "numeric", timeZone: "UTC",
  }).format(new Date(day + "T00:00:00Z"));
  const percent = (value: number) => formatNumber(value / 100, { style: "percent", maximumFractionDigits: 2 });
  const maximum = Math.max(1, ...(data?.history.results.flatMap((row) => [row.created, row.completed]) ?? []));
  return (
    <section className={styles.reports} aria-label={ui("Reports")}>
      <header className={styles.header}>
        <span className={styles.icon}><ReportIcon /></span>
        <div><h2>{ui("Reports")}</h2><p>{workspaceRole === "member" && !projectId ? ui("Reports from projects you belong to") : ui("Task progress, activity and workload")}</p></div>
        <button disabled={exporting || !data} onClick={() => void download()}>{exporting ? ui("Exporting…") : ui("Export CSV")}</button>
      </header>
      {exportError && <p role="alert" className={styles.error}>{ui(exportError)}</p>}
      <section className={styles.panel} aria-label={ui("Report filters")}>
        <div className={styles.presets} role="group" aria-label={ui("Date presets")}>
          {[7, 30, 90].map((days) => <button key={days} onClick={() => {
            setFilters((current) => ({ ...current, ...reportDateRange(days) }));
            setPage(1); setFormError("");
          }}>{ui("Last {0} days", days)}</button>)}
        </div>
        <form key={JSON.stringify(filters)} className={styles.filters} onSubmit={apply}>
          <label>{ui("Start date")}<input name="start" type="date" required defaultValue={filters.start_date} /></label>
          <label>{ui("End date")}<input name="end" type="date" required defaultValue={filters.end_date} /></label>
          <label>{ui("Assignee")}<select name="assignee" defaultValue={filters.assignee ?? ""}>
            <option value="">{ui("Anyone")}</option><option value="me">{ui("Me")}</option>
            {memberOptions.map((member) => <option key={member.user_id} value={member.user_id}>{member.user_email}</option>)}
          </select></label>
          <label>{ui("Status")}<select name="status" defaultValue={filters.status ?? ""}><option value="">{ui("All statuses")}</option>
            {["todo", "in_progress", "in_review", "done"].map((value) => <option key={value} value={value}>{ui(labels[value])}</option>)}
          </select></label>
          <label>{ui("Priority")}<select name="priority" defaultValue={filters.priority ?? ""}><option value="">{ui("All priorities")}</option>
            {["low", "medium", "high", "urgent"].map((value) => <option key={value} value={value}>{ui(labels[value])}</option>)}
          </select></label>
          <button className={styles.primary}>{ui("Apply filters")}</button>
        </form>
        {memberError && <p role="alert">{ui("Unable to load member names.")} <button onClick={() => setMemberRevision((value) => value + 1)}>{ui("Retry members")}</button></p>}
        {formError && <p role="alert" className={styles.error}>{ui(formError)}</p>}
        <p className={styles.hint}>{ui("Dates use UTC. Workload, comparisons and CSV filter tasks by creation date. History uses the assignee and status recorded at each activity.")}</p>
      </section>

      {!current ? <p role="status">{ui("Loading reports…")}</p> : current.error ? (
        <div className={styles.panel} role="alert"><p>{ui(current.error)}</p>
          <button onClick={() => setRevision((value) => value + 1)}>{ui("Try again")}</button>
        </div>
      ) : data && <>
        <section aria-label={ui("Current overview")}>
          <h3>{ui("Current overview")} <small>{ui("All dates · as of")} {formatDate(data.overview.as_of, { dateStyle: "medium", timeZone: "UTC" })}</small></h3>
          <div className={styles.metrics}>
            {(["total_tasks", "active_tasks", "completed_tasks", "overdue_tasks", "completion_rate"] as const).map((field) =>
              <article key={field}><span>{ui(field.replaceAll("_", " "))}</span><strong>{field === "completion_rate" ? percent(data.overview.summary[field]) : formatNumber(data.overview.summary[field])}</strong></article>)}
          </div>
        </section>
        <div className={styles.columns}>
          {(["status_distribution", "priority_distribution"] as const).map((distribution) => (
            <section className={styles.panel} key={distribution}>
              <h3>{distribution === "status_distribution" ? ui("Current status") : ui("Current priority")}</h3>
              {Object.entries(data.overview[distribution]).map(([value, count]) => (
                <div key={value} className={styles.distribution}><span>{ui(labels[value])}</span>
                  <meter min={0} max={Math.max(1, data.overview.summary.total_tasks)} value={count}>{formatNumber(count)}</meter><strong>{formatNumber(count)}</strong>
                </div>
              ))}
            </section>
          ))}
        </div>
        <section className={styles.panel} aria-label={ui("Historical activity")}>
          <div className={styles.sectionHeading}><h3>{ui("Historical activity")}</h3>
            <label>{ui("Group by")}<select value={granularity} onChange={(event) => setGranularity(event.target.value)}>
              <option value="day">{ui("Day")}</option><option value="week">{ui("Week")}</option>
            </select></label>
          </div>
          <p className={styles.hint}>{ui("Completion tracking since")} {data.history.completion_tracking_since ? formatDate(data.history.completion_tracking_since, { dateStyle: "medium", timeZone: "UTC" }) : ui("not available")}. {ui("Reopened tasks can contribute another completion. Partial weeks show only days inside the selected range.")}</p>
          <div className={styles.comparison}>
            {(["created", "completed"] as const).map((field) => <p key={field}><strong>{formatNumber(totals(data.history.results, field))}</strong> {ui(field)}
              <span>{ui("Previous period")} {formatNumber(totals(data.history.previous_results, field))}</span></p>)}
          </div>
          <div className={styles.legend}><span>{ui("● Created")}</span><span>{ui("● Completed")}</span></div>
          <p className={styles.hint}>{ui("Dates along the bottom show when activity occurred. Bar height shows the number of tasks. Select a date for exact counts.")}</p>
          <div className={styles.axisLabel}>{ui("Tasks · scale 0–")}{formatNumber(maximum)}</div>
          <div className={styles.chart} role="group" aria-label={ui("Created and completed tasks by date")}>
            {data.history.results.map((row) => <button type="button" className={styles.chartColumn} key={row.date}
              aria-pressed={selectedBucket === row.date} onClick={() => setSelectedBucket(row.date)}
              aria-label={ui("{0} through {1}: {2} created, {3} completed", formatDay(row.start_date), formatDay(row.end_date), row.created, row.completed)}
              title={ui("{0}–{1}: {2} created, {3} completed", formatDay(row.start_date), formatDay(row.end_date), row.created, row.completed)}>
              <div className={styles.bars}><span style={{ height: `${row.created * 100 / maximum}%` }} /><span style={{ height: `${row.completed * 100 / maximum}%` }} /></div>
              <small>{formatDay(row.date)}</small>
            </button>)}
          </div>
          {activeBucket && <p className={styles.bucketDetail} role="status">
            {formatDay(activeBucket.start_date)}–{formatDay(activeBucket.end_date)} · {formatNumber(activeBucket.created)} {ui("created ·")} {formatNumber(activeBucket.completed)} {ui("completed")}
          </p>}
          <details><summary>{ui("Activity data")}</summary><div className={styles.scroll}><table><thead><tr><th>{ui("From")}</th><th>{ui("Through")}</th><th>{ui("Created")}</th><th>{ui("Completed")}</th></tr></thead><tbody>
            {data.history.results.map((row) => <tr key={row.date}><td>{formatDay(row.start_date)}</td><td>{formatDay(row.end_date)}</td><td>{formatNumber(row.created)}</td><td>{formatNumber(row.completed)}</td></tr>)}
          </tbody></table></div></details>
        </section>
        <section className={styles.panel} aria-label={ui("Member workload")}>
          <h3>{ui("Member workload")}</h3><p className={styles.hint}>{ui("Current assignments for tasks matching the applied filters. Due soon includes today through seven days ahead.")}</p>
          {data.workload.length ? <div className={styles.scroll}><table><thead><tr>
            <th>{ui("Assignee")}</th><th>{ui("Active")}</th><th>{ui("Completed")}</th><th>{ui("Overdue")}</th><th>{ui("Due soon")}</th><th>{ui("Completion")}</th>
          </tr></thead><tbody>{data.workload.map((row) => <tr key={row.assignee ?? "unassigned"}>
            <td>{row.assignee === null ? ui("Former member") : memberOptions.find((member) => member.user_id === row.assignee)?.user_email ?? ui("User #{0}", row.assignee)}</td>
            <td>{formatNumber(row.active_tasks)}</td><td>{formatNumber(row.completed_tasks)}</td><td>{formatNumber(row.overdue_tasks)}</td><td>{formatNumber(row.due_soon_tasks)}</td><td>{percent(row.completion_rate)}</td>
          </tr>)}</tbody></table></div> : <p>{ui("No tasks match these filters.")}</p>}
        </section>
        {data.ranking && <section className={styles.panel} aria-label={ui("Project comparison")}>
          <div className={styles.sectionHeading}><h3>{ui("Project comparison")}</h3>
            <label>{ui("Order by")}<select value={ordering} onChange={(event) => { setOrdering(event.target.value); setPage(1); }}>
              {["name", "-name", "total_tasks", "-total_tasks", "completed_tasks", "-completed_tasks", "overdue_tasks", "-overdue_tasks"].map((value) =>
                <option key={value} value={value}>{ui(value.replace("-", "").replaceAll("_", " "))} {value.startsWith("-") ? "↓" : "↑"}</option>)}
            </select></label>
          </div>
          <div className={styles.scroll}><table><thead><tr><th>{ui("Project")}</th><th>{ui("Tasks")}</th><th>{ui("Completed")}</th><th>{ui("Overdue")}</th><th>{ui("Completion")}</th></tr></thead><tbody>
            {data.ranking.results.map((row) => <tr key={row.project_id}><td><Link href={`/dashboard/workspaces/${encodeURIComponent(slug)}/projects/${row.project_id}/reports`}>{row.project_name}</Link></td>
              <td>{formatNumber(row.total_tasks)}</td><td>{formatNumber(row.completed_tasks)}</td><td>{formatNumber(row.overdue_tasks)}</td><td>{percent(row.completion_rate)}</td></tr>)}
          </tbody></table></div>
          {!data.ranking.count && <p>{ui("No accessible projects.")}</p>}
          <footer className={styles.pagination}><span>{ui("{0} projects · Page {1}", data.ranking.count, page)}</span><div>
            <button disabled={!data.ranking.previous} onClick={() => setPage(page - 1)}>{ui("Previous")}</button>
            <button disabled={!data.ranking.next} onClick={() => setPage(page + 1)}>{ui("Next")}</button>
          </div></footer>
        </section>}
      </>}
    </section>
  );
}
