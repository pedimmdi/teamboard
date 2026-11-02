import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(
  new URL("../src/lib/api.ts", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;

const permissionsSource = readFileSync(
  new URL(
    "../src/app/dashboard/workspaces/[slug]/projects/project-utils.ts",
    import.meta.url,
  ),
  "utf8",
);
const permissionExports = {};
runInNewContext(
  ts.transpileModule(permissionsSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText,
  { exports: permissionExports, Intl, Date },
);

test("workspace owners and admins retain all management rights for every project role", () => {
  for (const workspaceRole of ["owner", "admin"]) {
    for (const projectRole of [null, "member", "manager"]) {
      const rights = permissionExports.projectPermissions(
        workspaceRole,
        projectRole,
      );
      for (const action of [
        "canCreate",
        "canManage",
        "canAssignManagers",
        "canDelete",
      ])
        assert.equal(rights[action], true);
      assert.equal(rights.canLeave, projectRole !== null);
    }
  }
});

test("regular managers manage details and members without assigning managers or deleting projects", () => {
  const rights = permissionExports.projectPermissions("member", "manager");
  assert.equal(rights.canManage, true);
  assert.equal(rights.canLeave, true);
  for (const action of ["canCreate", "canAssignManagers", "canDelete"])
    assert.equal(rights[action], false);
});

test("regular members are read only and missing workspace membership grants no actions", () => {
  for (const [workspaceRole, projectRole] of [
    ["member", "member"],
    ["member", null],
    [null, "manager"],
    [null, null],
  ]) {
    const rights = permissionExports.projectPermissions(
      workspaceRole,
      projectRole,
    );
    for (const action of [
      "canCreate",
      "canManage",
      "canAssignManagers",
      "canDelete",
    ])
      assert.equal(rights[action], false);
    assert.equal(
      rights.canLeave,
      workspaceRole !== null && projectRole !== null,
    );
  }
});

test("Figma navigation assets are non-empty local SVGs at their native size", () => {
  for (const name of [
    "folder",
    "users",
    "settings",
    "chevron-right",
    "chevrons-up-down",
  ]) {
    const root = readFileSync(
      new URL(`../public/icons/${name}.svg`, import.meta.url),
      "utf8",
    ).split(">")[0];
    assert.match(root, /<svg\s/);
    assert.match(root, /width="20"/);
    assert.match(root, /height="20"/);
  }
});
function client(
  responder = () =>
    new Response(JSON.stringify({ id: "project" }), {
      headers: { "Content-Type": "application/json" },
    }),
) {
  const calls = [];
  const exports = {};
  runInNewContext(code, {
    exports,
    process: { env: { NEXT_PUBLIC_API_URL: "http://api.test" } },
    URLSearchParams,
    FormData,
    File,
    fetch: async (url, options) => {
      calls.push({ url, ...options });
      return responder(url, options);
    },
  });
  return { api: exports, calls };
}

test("projects use the workspace scope, encoded path segments, and access token", async () => {
  const { api, calls } = client();
  await api.getProjects("access", "team / one", 2);
  assert.equal(
    calls[0].url,
    "http://api.test/api/v1/workspaces/team%20%2F%20one/projects/?page=2",
  );
  assert.equal(calls[0].headers.Authorization, "Bearer access");
  assert.equal(calls[0].credentials, "include");
});

test("create and update send only the supplied project details", async () => {
  const { api, calls } = client();
  await api.createProject("access", "team", {
    name: "Website",
    description: "New site",
  });
  await api.updateProject("access", "team", "project", {
    description: "Changed",
  });
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(JSON.parse(calls[0].body), {
    name: "Website",
    description: "New site",
  });
  assert.equal(calls[1].method, "PATCH");
  assert.deepEqual(JSON.parse(calls[1].body), { description: "Changed" });
  assert.equal(
    calls[1].url,
    "http://api.test/api/v1/workspaces/team/projects/project/",
  );
});

test("member mutations use membership IDs and manager/member roles", async () => {
  const { api, calls } = client();
  await api.addProjectMember("access", "team", "project", 17, "manager");
  await api.updateProjectMemberRole(
    "access",
    "team",
    "project",
    "membership",
    "member",
  );
  await api.removeProjectMember("access", "team", "project", "membership");
  assert.deepEqual(JSON.parse(calls[0].body), { user_id: 17, role: "manager" });
  assert.equal(
    calls[1].url,
    "http://api.test/api/v1/workspaces/team/projects/project/members/membership/role/",
  );
  assert.deepEqual(JSON.parse(calls[1].body), { role: "member" });
  assert.equal(calls[2].method, "DELETE");
  assert.equal(
    calls[2].url,
    "http://api.test/api/v1/workspaces/team/projects/project/members/membership/",
  );
});

test("leave and delete accept empty 204 responses", async () => {
  const { api, calls } = client(() => new Response(null, { status: 204 }));
  assert.equal(await api.leaveProject("access", "team", "project"), null);
  assert.equal(await api.deleteProject("access", "team", "project"), null);
  assert.equal(calls[0].method, "POST");
  assert.equal(
    calls[0].url,
    "http://api.test/api/v1/workspaces/team/projects/project/leave/",
  );
  assert.equal(calls[1].method, "DELETE");
});

for (const status of [400, 403, 404, 409, 429]) {
  test(`project errors preserve status ${status} and the server's explanation`, async () => {
    const detail = "Assign another manager before leaving.";
    const { api } = client(
      () =>
        new Response(JSON.stringify({ detail }), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    );
    await assert.rejects(
      api.leaveProject("access", "team", "project"),
      (error) => error.status === status && error.message === detail,
    );
  });
}

test("duplicate project names retain field validation for inline feedback", async () => {
  const { api } = client(
    () =>
      new Response(
        JSON.stringify({ name: ["A project with this name already exists."] }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
  );
  await assert.rejects(
    api.createProject("access", "team", { name: "Website", description: "" }),
    (error) =>
      error.errors.name[0] === "A project with this name already exists.",
  );
});
