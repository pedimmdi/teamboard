import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("../src/app/dashboard/dashboard-workspace.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
class ApiError extends Error {
  constructor(status) {
    super("Request failed");
    this.status = status;
  }
}

function navigation({
  getWorkspace = async (_, slug) => ({ slug }),
  getWorkspaces = async () => ({ results: [{ slug: "first" }] }),
} = {}) {
  const exports = {};
  runInNewContext(code, {
    exports,
    require: () => ({ ApiError, getWorkspace, getWorkspaces }),
  });
  return exports;
}

test("workspace in the route takes precedence over a saved workspace", async () => {
  assert.equal(
    (await navigation().loadDashboardWorkspace("token", "current", "saved"))
      .slug,
    "current",
  );
});

test("account pages restore and validate the last selected workspace", async () => {
  assert.equal(
    (await navigation().loadDashboardWorkspace("token", undefined, "saved"))
      .slug,
    "saved",
  );
});

test("first visit selects an accessible workspace and empty accounts keep navigation unselected", async () => {
  assert.equal(
    (await navigation().loadDashboardWorkspace("token")).slug,
    "first",
  );
  assert.equal(
    await navigation({
      getWorkspaces: async () => ({ results: [] }),
    }).loadDashboardWorkspace("token"),
    null,
  );
});

test("a deleted or inaccessible saved workspace falls back to an accessible workspace", async () => {
  const api = navigation({
    getWorkspace: async () => {
      throw new ApiError(404);
    },
  });
  assert.equal(
    (await api.loadDashboardWorkspace("token", undefined, "removed")).slug,
    "first",
  );
  assert.equal(
    await api.loadDashboardWorkspace("token", "removed", "saved"),
    null,
  );
});

test("network and server errors do not silently choose a different workspace", async () => {
  for (const error of [new ApiError(500), new Error("Offline")]) {
    await assert.rejects(
      navigation({
        getWorkspace: async () => {
          throw error;
        },
      }).loadDashboardWorkspace("token", undefined, "saved"),
      (e) => e === error,
    );
  }
});

test("saved selection is isolated per account", () => {
  assert.notEqual(
    navigation().dashboardWorkspaceKey(1),
    navigation().dashboardWorkspaceKey(2),
  );
});
