import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

function compile(path) {
  return ts.transpileModule(
    readFileSync(new URL(path, import.meta.url), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
}
const apiCode = compile("../src/lib/api.ts");
const utils = {};
runInNewContext(
  compile(
    "../src/app/dashboard/workspaces/[slug]/projects/[projectId]/tasks/task-utils.ts",
  ),
  { exports: utils, URLSearchParams, Date, Intl },
);

function moveClient() {
  const calls = [];
  const exports = {};
  const api = {
    getTask: () => { throw new Error("Client must not read positions before moving"); },
    getTasks: () => { throw new Error("Client must not read column counts before moving"); },
    moveTask: async (...args) => { calls.push(args); return { id: "task" }; },
  };
  runInNewContext(compile("../src/app/dashboard/workspaces/[slug]/projects/[projectId]/tasks/task-moves.ts"), { exports, require: () => api });
  return { move: exports.moveTaskToPosition, calls };
}

test("drop targets are sent by ID without a client-side position snapshot", async () => {
  const { move, calls } = moveClient();
  await move("token", "team", "project", "task", "todo", "target");
  assert.deepEqual(calls[0].slice(0,5), ["token", "team", "project", "task", "todo"]);
  assert.equal(JSON.stringify(calls[0][5]), JSON.stringify({ before_task: "target" }));
});

test("column endpoints are resolved by the server for first and last placement", async () => {
  const { move, calls } = moveClient();
  await move("token", "team", "project", "task", "done");
  await move("token", "team", "project", "task", "done", null, true);
  assert.equal(JSON.stringify(calls[0][5]), JSON.stringify({ placement: "last" }));
  assert.equal(JSON.stringify(calls[1][5]), JSON.stringify({ placement: "first" }));
});
function client(
  response = () =>
    new Response(JSON.stringify({ id: "task" }), {
      headers: { "Content-Type": "application/json" },
    }),
) {
  const api = {},
    calls = [];
  runInNewContext(apiCode, {
    exports: api,
    process: { env: { NEXT_PUBLIC_API_URL: "http://api.test" } },
    URLSearchParams,
    FormData,
    File,
    fetch: async (url, options) => {
      calls.push({ url, ...options });
      return response();
    },
  });
  return { api, calls };
}

test("task filtering sends encoded project scope, multiple statuses, assignee, dates, and pagination", async () => {
  const { api, calls } = client();
  await api.getTasks("access", "team / 1", "project/2", {
    page: 2,
    page_size: 4,
    status: ["todo", "in_review"],
    assignee: "me",
    search: "token & refresh",
    ordering: "-priority",
    overdue: true,
    due_before: "2026-11-10",
  });
  const url = new URL(calls[0].url);
  assert.equal(
    url.pathname,
    "/api/v1/workspaces/team%20%2F%201/projects/project%2F2/tasks/",
  );
  for (const [key, value] of Object.entries({
    page: "2",
    page_size: "4",
    status: "todo,in_review",
    assignee: "me",
    search: "token & refresh",
    ordering: "-priority",
    overdue: "true",
    due_before: "2026-11-10",
  }))
    assert.equal(url.searchParams.get(key), value);
  assert.equal(calls[0].headers.Authorization, "Bearer access");
});
test("empty filters are omitted and unassigned is represented without an assignee", async () => {
  const { api, calls } = client();
  await api.getTasks("access", "team", "project", {
    status: [],
    search: "",
    priority: undefined,
    unassigned: true,
  });
  const query = new URL(calls[0].url).searchParams;
  assert.equal(query.get("unassigned"), "true");
  for (const key of ["status", "search", "priority", "assignee"])
    assert.equal(query.has(key), false);
});
test("task create and partial updates preserve explicit removal of assignee and due date", async () => {
  const { api, calls } = client();
  await api.createTask("access", "team", "project", {
    title: "Task",
    description: "Details",
    status: "todo",
    priority: "medium",
    assignee: 7,
    due_date: "2026-11-10",
  });
  await api.updateTask("access", "team", "project", "task", {
    assignee: null,
    due_date: null,
  });
  assert.equal(calls[0].method, "POST");
  assert.equal(JSON.parse(calls[0].body).assignee, 7);
  assert.equal(calls[1].method, "PATCH");
  assert.deepEqual(JSON.parse(calls[1].body), {
    assignee: null,
    due_date: null,
  });
});
test("task retrieval, atomic moves, and deletion use the task-scoped endpoints", async () => {
  const { api, calls } = client();
  await api.getTask("access", "team", "project", "task/1");
  await api.moveTask("access", "team", "project", "task/1", "in_review", 3);
  assert.match(calls[0].url, /tasks\/task%2F1\/$/);
  assert.match(calls[1].url, /tasks\/task%2F1\/move\/$/);
  assert.equal(calls[1].method, "POST");
  assert.deepEqual(JSON.parse(calls[1].body), {
    status: "in_review",
    position: 3,
  });
  const deletion = client(() => new Response(null, { status: 204 }));
  assert.equal(
    await deletion.api.deleteTask("access", "team", "project", "task"),
    null,
  );
  assert.equal(deletion.calls[0].method, "DELETE");
});
for (const status of [403, 404, 409, 429])
  test(`task failures retain server status ${status} and explanation`, async () => {
    const { api } = client(
      () =>
        new Response(
          JSON.stringify({ detail: "Only project managers can delete tasks." }),
          { status, headers: { "Content-Type": "application/json" } },
        ),
    );
    await assert.rejects(
      api.deleteTask("access", "team", "project", "task"),
      (e) =>
        e.status === status &&
        e.message === "Only project managers can delete tasks.",
    );
  });
test("invalid assignee and title validation remain available for inline form errors", async () => {
  const { api } = client(
    () =>
      new Response(
        JSON.stringify({
          title: ["Task title cannot be empty."],
          assignee: ["Invalid assignee for this project."],
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
  );
  await assert.rejects(
    api.updateTask("access", "team", "project", "task", { title: "" }),
    (e) =>
      e.errors.title[0] === "Task title cannot be empty." &&
      e.errors.assignee[0] === "Invalid assignee for this project.",
  );
});
test("filter URLs reject malformed values and preserve valid multi-status and member filters", () => {
  const filters = utils.readTaskFilters(
    new URLSearchParams(
      "status=todo,invalid,done,todo&priority=urgent&assignee=7&ordering=-priority&due_before=2026-02-31",
    ),
  );
  assert.equal(
    JSON.stringify(filters.statuses),
    JSON.stringify(["todo", "done"]),
  );
  assert.equal(filters.assignee, "7");
  assert.equal(filters.dueBefore, "");
  assert.equal(filters.ordering, "-priority");
  assert.equal(
    utils.readTaskFilters(
      new URLSearchParams("ordering=invalid&assignee=-1&priority=invalid"),
    ).ordering,
    "due_date",
  );
});
test("changing filters resets the page while retaining the open task and view", () => {
  const filters = {
    ...utils.emptyTaskFilters,
    assignee: "unassigned",
    statuses: ["in_progress"],
    search: "refresh",
    overdue: true,
  };
  const url = utils.writeTaskFilters(
    filters,
    new URLSearchParams("page=3&view=list&task=abc&assignee=me"),
  );
  assert.equal(url.has("page"), false);
  assert.equal(url.has("assignee"), false);
  assert.equal(url.get("unassigned"), "true");
  assert.equal(url.get("task"), "abc");
  assert.equal(url.get("view"), "list");
  assert.equal(
    JSON.stringify(utils.readTaskFilters(url)),
    JSON.stringify(filters),
  );
});
test("overdue calculations use calendar days and ignore completed tasks and today's date", () => {
  const today = new Date("2026-11-05T23:59:00Z");
  assert.equal(utils.overdueDays("2026-11-03", "todo", today), 2);
  assert.equal(utils.overdueDays("2026-11-05", "todo", today), 0);
  assert.equal(utils.overdueDays("2026-11-03", "done", today), 0);
  assert.equal(utils.overdueDays(null, "todo", today), 0);
});
test("task edits send changed fields only and distinguish unchanged values from clearing them", () => {
  const input = {
    ...utils.taskInput(),
    title: "Task",
    assignee: 7,
    due_date: "2026-11-10",
  };
  assert.equal(JSON.stringify(utils.taskChanges(input, input)), "{}");
  assert.equal(
    JSON.stringify(
      utils.taskChanges(input, { ...input, assignee: null, due_date: null }),
    ),
    JSON.stringify({ assignee: null, due_date: null }),
  );
});

test("overdue uses the UTC day when local calendars disagree around midnight", () => {
  const east = new Date("2026-11-05T21:30:00Z");
  east.getFullYear = () => 2026; east.getMonth = () => 10; east.getDate = () => 6;
  assert.equal(utils.overdueDays("2026-11-05", "todo", east), 0);
  const west = new Date("2026-11-05T01:00:00Z");
  west.getFullYear = () => 2026; west.getMonth = () => 10; west.getDate = () => 4;
  assert.equal(utils.overdueDays("2026-11-04", "todo", west), 1);
  assert.equal(utils.overdueDays("2026-11-04", "done", west), 0);
});
test("move API serializes anchor and boundary targets without numeric positions", async () => {
  const { api, calls } = client();
  await api.moveTask("access", "team", "project", "task", "todo", { before_task: "target" });
  await api.moveTask("access", "team", "project", "task", "done", { placement: "last" });
  assert.deepEqual(JSON.parse(calls[0].body), { status: "todo", before_task: "target" });
  assert.deepEqual(JSON.parse(calls[1].body), { status: "done", placement: "last" });
});
