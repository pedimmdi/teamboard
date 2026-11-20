import type { InboxNotification } from "@/lib/api";

const events = {
  task_assigned: ["You were assigned to a task", "✓", "task"],
  task_reminder: ["Task reminder", "◷", "task"],
  task_updated: ["A task assigned to you was updated", "↻", "task"],
  comment_mentioned: ["You were mentioned in a comment", "@", "comment"],
  comment_replied: ["Someone replied to your comment", "↪", "comment"],
  workspace_invited: ["You have a new workspace invitation", "+", "workspace"],
  workspace_role_changed: ["Your workspace role was updated", "↕", "workspace"],
  project_member_added: ["You were added to a project", "+", "project"],
  project_role_changed: ["Your project role was updated", "↕", "project"],
} as const;

export function notificationContent(notification: InboxNotification) {
  const [title, icon, tone] = events[notification.event_type] ??
    ["New activity", "•", "task"];
  const { workspace_slug, project, task, payload } = notification;
  const workspace = workspace_slug
    ? `/dashboard/workspaces/${encodeURIComponent(workspace_slug)}`
    : null;
  const projectPath = workspace && project
    ? `${workspace}/projects/${encodeURIComponent(project)}`
    : null;
  let href = projectPath ?? (workspace ? `${workspace}/projects` : null);
  if (projectPath && task) {
    href = `${projectPath}/tasks?task=${encodeURIComponent(task)}`;
  }
  if (notification.event_type === "workspace_invited") href = null;
  if (notification.event_type === "workspace_role_changed" && workspace) {
    href = `${workspace}/members`;
  }

  const role = [payload.old_role, payload.new_role]
    .filter(Boolean).join(" → ") || payload.role;
  return {
    title,
    icon,
    tone,
    href,
    description: [
      notification.actor_name,
      notification.task_title,
      notification.project_name,
      notification.workspace_name,
      role,
    ].filter(Boolean).join(" · "),
  };
}
