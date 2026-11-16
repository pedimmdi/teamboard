import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function load(path, globals = {}) {
  const exports = {};
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, { exports, ...globals });
  return exports;
}

test("calendar uses UTC days, Monday weeks and an exclusive overlap end", () => {
  const { monthDays, itemsForDay } = load("../src/components/calendar/calendar-dates.ts");
  const days = monthDays(new Date("2026-11-01T00:00:00Z"));
  assert.equal(days[0].toISOString(), "2026-10-26T00:00:00.000Z");
  assert.equal(days.length, 42);
  const item = { starts_at: "2026-11-01T00:00:00Z", ends_at: "2026-11-02T00:00:00Z" };
  assert.equal(itemsForDay([item], days[6]).length, 1);
  assert.equal(itemsForDay([item], days[7]).length, 0);
});

test("calendar API uses the workspace and project URLs and event methods", async () => {
  const requests = [];
  const api = load("../src/lib/api.ts", {
    process: { env: { NEXT_PUBLIC_API_URL: "http://localhost:8000" } },
    FormData, URLSearchParams,
    fetch: async (url, options) => {
      requests.push([new URL(url), options]);
      return Response.json({});
    },
  });
  await api.getCalendarTimeline("token", "team", "start", "end");
  await api.getCalendarTimeline("token", "team", "start", "end", "project");
  await api.getCalendarEvent("token", "team", "project", "event");
  await api.saveCalendarEvent("token", "team", "project", { title: "Meeting" });
  await api.saveCalendarEvent("token", "team", "project", { title: "Meeting" }, "event");
  await api.deleteCalendarEvent("token", "team", "project", "event");
  assert.deepEqual(requests.map(([url, options]) => [url.pathname + url.search, options.method ?? "GET"]), [
    ["/api/v1/workspaces/team/calendar/timeline/?start=start&end=end", "GET"],
    ["/api/v1/workspaces/team/projects/project/calendar/timeline/?start=start&end=end", "GET"],
    ["/api/v1/workspaces/team/projects/project/calendar/event/", "GET"],
    ["/api/v1/workspaces/team/projects/project/calendar/", "POST"],
    ["/api/v1/workspaces/team/projects/project/calendar/event/", "PATCH"],
    ["/api/v1/workspaces/team/projects/project/calendar/event/", "DELETE"],
  ]);
});
