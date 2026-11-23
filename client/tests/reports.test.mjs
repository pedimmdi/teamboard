import assert from "node:assert/strict";
import { loadSource } from "./load-source.mjs";
import test from "node:test";


test("report date ranges use UTC inclusive days and reject oversized or reversed ranges", () => {
  const dates = loadSource("../src/components/reports/report-utils.ts");
  const range = dates.reportDateRange(7, new Date("2026-03-09T00:30:00Z"));
  assert.equal(range.start_date, "2026-03-03");
  assert.equal(range.end_date, "2026-03-09");
  assert.equal(dates.validateReportDates("2026-01-01", "2026-01-01"), true);
  assert.equal(dates.validateReportDates("2026-02-01", "2026-01-01"), false);
  assert.equal(dates.validateReportDates("2025-01-01", "2026-01-02"), false);
});

test("report requests preserve scope, applied filters, pagination and CSV response type", async () => {
  const calls = [];
  const api = loadSource("../src/lib/api.ts", {
    process: { env: { NEXT_PUBLIC_API_URL: "http://localhost:8000" } }, FormData, URLSearchParams,
    fetch: async (url, options) => {
      calls.push([new URL(url), options]);
      return String(url).includes("export/") ? new Response("task_id,title", { headers: { "Content-Type": "text/csv" } }) : Response.json({});
    },
  });
  const filters = { start_date: "2026-01-01", end_date: "2026-01-31", assignee: "me", priority: "urgent", status: "" };
  await api.getReportOverview("token", "team/one", "project");
  await api.getReportHistory("token", "team/one", { ...filters, granularity: "week" }, "project");
  await api.getReportWorkload("token", "team/one", filters);
  await api.getReportRanking("token", "team/one", filters, 2, "-overdue_tasks");
  const blob = await api.exportReport("token", "team/one", filters, "project");
  assert.equal(await blob.text(), "task_id,title");
  assert.equal(calls[0][0].pathname, "/api/v1/workspaces/team%2Fone/projects/project/reports/");
  assert.equal(calls[1][0].searchParams.get("granularity"), "week");
  assert.equal(calls[2][0].searchParams.get("status"), null);
  assert.equal(calls[3][0].searchParams.get("page"), "2");
  assert.equal(calls[3][0].searchParams.get("ordering"), "-overdue_tasks");
  for (const [, options] of calls) assert.equal(options.headers.Authorization, "Bearer token");
});
