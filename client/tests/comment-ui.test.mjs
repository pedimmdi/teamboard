import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import ts from "typescript";

test("drawer opens Comments first and a reply jumps to its parent", async () => {
  const dom = new JSDOM("<main></main>");
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const { createRoot } = await import("react-dom/client");
  const container = document.querySelector("main");
  const root = createRoot(container);
  const calls = [];
  dom.window.HTMLElement.prototype.scrollIntoView = function () {
    calls.push(this.id);
  };
  const user = { id: 1, email: "user@example.com", first_name: "Alex", last_name: "" };
  const timestamp = "2026-11-12T10:00:00Z";
  const parent = { id: "parent", body: "Original comment", author_id: 1, author_name: "Alex", created_at: timestamp, updated_at: timestamp, mentions: [] };
  const reply = { ...parent, id: "reply", body: "A reply", reply_to: parent.id };
  const api = {
    getTask: async () => ({ id: "task", title: "Test task", priority: "medium", status: "todo", created_at: timestamp, updated_at: timestamp }),
    getTaskComments: async () => ({ results: [parent, reply], count: 2, next: null }),
  };
  const styles = new Proxy({}, { get: (_, name) => name === "__esModule" ? false : String(name) });
  const component = (name, modules) => {
    const source = readFileSync(new URL("../src/app/dashboard/workspaces/[slug]/projects/[projectId]/tasks/" + name + ".tsx", import.meta.url), "utf8");
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
    });
    const exports = {};
    runInNewContext(outputText, {
      exports, React, document, window, Intl, Date,
      require: (path) => path.endsWith(".css") ? styles : modules[path],
    });
    return exports.default;
  };
  const Stub = () => null;
  const Comments = component("task-comments", {
    react: React, "@/lib/api": api, "next/image": Stub, "@/components/ui/Avatar": Stub,
    "./comment-input": Stub, "./comment-actions": Stub,
  });
  const Drawer = component("task-drawer", {
    react: React, "@/lib/api": api, "@/lib/auth": { useAuth: () => ({ user }) },
    "./task-dialog": ({ children }) => React.createElement("section", null, children),
    "./task-comments": Comments, "./task-form": () => React.createElement("p", null, "Task details"),
    "./task-icons": Stub,
    "./task-utils": { taskInput: () => ({}), taskStatuses: [] },
  });
  try {
    await act(async () => root.render(React.createElement(Drawer, {
      token: "test", slug: "team", projectId: "project", taskId: "task", members: [],
      onCommentCountChange: () => {}, onMissing: () => {},
    })));
    const buttons = () => [...container.querySelectorAll("button")];
    const commentsTab = buttons().find((button) => button.textContent.includes("Comments (2)"));
    const detailsTab = buttons().find((button) => button.textContent.trim() === "Details");
    assert.ok(commentsTab.compareDocumentPosition(detailsTab) & 4);
    assert.equal(commentsTab.getAttribute("aria-pressed"), "true");
    assert.equal(container.querySelector("#comment-reply").className, "reply");
    await act(async () => buttons().find((button) => button.textContent.includes("Reply to Alex")).click());
    assert.equal(document.activeElement.id, "comment-parent");
    assert.deepEqual(calls, ["comment-parent"]);
    await act(async () => detailsTab.click());
    assert.equal(detailsTab.getAttribute("aria-pressed"), "true");
    assert.equal(container.querySelector("[data-comment-thread]").hidden, true);
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
    delete globalThis.window;
    delete globalThis.document;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});
