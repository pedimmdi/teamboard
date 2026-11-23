import assert from "node:assert/strict";
import test from "node:test";
import { loadSource } from "./load-source.mjs";


test("notification API sends filters, pagination, bearer credentials and read mutations", async () => {
  const requests = [];
  const api = loadSource("../src/lib/api.ts", {
    process: { env: { NEXT_PUBLIC_API_URL: "http://localhost:8000" } },
    FormData, URLSearchParams,
    fetch: async (url, options) => {
      requests.push([new URL(url), options]);
      return Response.json({});
    },
  });
  await api.getNotifications("token", "all");
  await api.getNotifications("token", "unread", 2);
  await api.getNotifications("token", "read");
  await api.getUnreadNotificationCount("token");
  await api.markNotificationRead("token", "notification/id");
  await api.markAllNotificationsRead("token");

  assert.deepEqual(requests.map(([url, options]) => [
    url.pathname + url.search, options.method ?? "GET", options.headers.Authorization,
  ]), [
    ["/api/v1/notifications/?page=1&page_size=20", "GET", "Bearer token"],
    ["/api/v1/notifications/?page=2&page_size=20&read=false", "GET", "Bearer token"],
    ["/api/v1/notifications/?page=1&page_size=20&read=true", "GET", "Bearer token"],
    ["/api/v1/notifications/unread-count/", "GET", "Bearer token"],
    ["/api/v1/notifications/notification%2Fid/mark-read/", "POST", "Bearer token"],
    ["/api/v1/notifications/mark-all-read/", "POST", "Bearer token"],
  ]);
});

test("task notifications open the task drawer and invitations use the email flow", () => {
  const { notificationContent } = loadSource("../src/app/dashboard/notifications/notification-content.ts");
  const notification = {
    event_type: "comment_replied",
    workspace_slug: "workspace",
    project: "project",
    task: "task",
    task_title: "Review changes",
    project_name: "API",
    workspace_name: "Core",
    payload: {},
  };
  const task = notificationContent(notification);
  assert.equal(task.href, "/dashboard/workspaces/workspace/projects/project/tasks?task=task");
  assert.equal(task.description, "Review changes · API · Core");

  const invitation = notificationContent({
    ...notification, event_type: "workspace_invited", project: null, task: null,
    project_name: null, task_title: null,
  });
  assert.equal(invitation.href, null);
  assert.equal(invitation.description, "Core");
});


test("task reminder notifications link directly to the existing task drawer", () => {
  const exports = loadSource("../src/app/dashboard/notifications/notification-content.ts");
  const content = exports.notificationContent({event_type:"task_reminder",workspace_slug:"team",project:"project",task:"task",payload:{},task_title:"Reminder task"});
  assert.equal(content.title,"Task reminder");
  assert.equal(content.href,"/dashboard/workspaces/team/projects/project/tasks?task=task");
});

test("Persian notification titles and role changes preserve workspace names and link destinations", () => {
  const { notificationContent } = loadSource("../src/app/dashboard/notifications/notification-content.ts");
  const notification = {
    event_type: "workspace_role_changed",
    workspace_slug: "design",
    workspace_name: "Design team",
    payload: { old_role: "member", new_role: "admin" },
  };
  assert.equal(notificationContent(notification, "en").description, "Design team · member → admin");
  const content = notificationContent(notification, "fa");
  assert.equal(content.title, "نقش شما در فضای کاری تغییر کرد");
  assert.equal(content.description, "Design team · عضو ← مدیر");
  assert.equal(content.href, "/dashboard/workspaces/design/members");
});
