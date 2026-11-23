import assert from "node:assert/strict";
import test from "node:test";
import { loadSource } from "./load-source.mjs";


const iran = loadSource("../src/lib/iran-time.ts", { Intl, Date });
const dates = loadSource("../src/components/calendar/calendar-dates.ts", {
  Date,
  require: (path) => path === "@/lib/iran-time" ? iran : undefined,
});

test("calendar uses UTC days, Monday weeks and an exclusive overlap end", () => {
  const { monthDays, itemsForDay } = dates;
  const days = monthDays(new Date("2026-11-01T00:00:00Z"));
  assert.equal(days[0].toISOString(), "2026-10-26T00:00:00.000Z");
  assert.equal(days.length, 42);
  const item = { starts_at: "2026-11-01T00:00:00Z", ends_at: "2026-11-02T00:00:00Z" };
  assert.equal(itemsForDay([item], days[6]).length, 1);
  assert.equal(itemsForDay([item], days[7]).length, 0);
});

test("Persian calendar starts on Saturday and moves between Solar Hijri months", () => {
  const { dayOfMonth, monthDays, monthStart, adjacentMonth } = dates;
  const nowruz = new Date("2026-03-21T00:00:00Z");
  const month = monthDays(nowruz, "persian", 6);
  assert.equal(month[0].toISOString(), nowruz.toISOString());
  assert.equal(dayOfMonth(nowruz, "persian"), 1);
  assert.equal(monthStart(month[14], "persian").toISOString(), nowruz.toISOString());
  assert.equal(adjacentMonth(nowruz, 1, "persian").toISOString(), "2026-04-21T00:00:00.000Z");
  assert.equal(adjacentMonth(nowruz, -1, "persian").toISOString(), "2026-02-20T00:00:00.000Z");
});

test("calendar API uses the workspace and project URLs and event methods", async () => {
  const requests = [];
  const api = loadSource("../src/lib/api.ts", {
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

test("project members can create and edit calendar events while deletion requires management", () => {
  const { calendarEventPermissions } = dates;
  for (const [workspace, project, expected] of [
    ["member", "member", [true, true, false]],
    ["member", "manager", [true, true, true]],
    ["member", null, [false, false, false]],
    ["owner", null, [true, true, true]],
    ["admin", null, [true, true, true]],
    [null, "member", [false, false, false]],
  ]) {
    const permissions = calendarEventPermissions(workspace, project);
    assert.deepEqual(Object.values(permissions), expected);
  }
});

test("all-day edits retain the last covered date across a month boundary", () => {
  const { toggleEventDates, itemsForDay } = dates;
  const start = "2026-10-31T09:00";
  const end = "2026-11-02T00:00";
  const allDayDates = Array.from(toggleEventDates(start, end, true));
  assert.deepEqual(allDayDates, ["2026-10-31", "2026-11-01"]);
  assert.deepEqual(Array.from(toggleEventDates(...allDayDates, false)), [start, "2026-11-01T10:00"]);
  const item = { starts_at: "2026-10-31T09:00-04:00", ends_at: "2026-11-01T19:00-05:00" };
  assert.equal(itemsForDay([item], new Date("2026-11-01")).length, 1);
  assert.equal(itemsForDay([item], new Date("2026-11-02")).length, 0);
});

test("Iran midnight groups timed events and keeps date-only records on their civil day", () => {
  const { iranCivilDay, iranInstant, iranWallClock } = iran;
  const { itemsForDay, timelineBounds } = dates;
  const now = new Date("2026-11-22T21:10:00Z");
  const monday = iranCivilDay(now);
  const tuesday = new Date("2026-11-24T00:00:00Z");
  assert.equal(monday.toISOString(), "2026-11-23T00:00:00.000Z");
  assert.equal(iranWallClock(now), "2026-11-23T00:40");
  assert.equal(iranInstant("2030-03-21T09:00").toISOString(), "2030-03-21T05:30:00.000Z");
  assert.equal(iranInstant("2030-02-31T09:00"), null);
  assert.deepEqual(Array.from(timelineBounds(monday, tuesday, true)), ["2026-11-22T20:30:00.000Z", "2026-11-24T00:00:00.000Z"]);
  const previous = { item_type: "event", starts_at: "2026-11-22T20:00:00Z", ends_at: "2026-11-22T20:30:00Z" };
  const overnight = { item_type: "event", starts_at: "2026-11-22T20:30:00Z", ends_at: "2026-11-22T21:30:00Z" };
  const due = { item_type: "task", starts_at: "2026-11-22T00:00:00Z", ends_at: "2026-11-23T00:00:00Z" };
  const allDay = { item_type: "event", all_day: true, starts_at: "2026-11-23T00:00:00Z", ends_at: "2026-11-24T00:00:00Z" };
  assert.deepEqual(Array.from(itemsForDay([previous, overnight, due, allDay], monday, true)), [overnight, allDay]);
  assert.deepEqual(Array.from(itemsForDay([previous, overnight, due, allDay], tuesday, true)), []);
});
