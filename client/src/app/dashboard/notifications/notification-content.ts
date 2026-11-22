import type { InboxNotification } from "@/lib/api";
import type { Locale } from "@/lib/locale";

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

const persianTitles: Record<keyof typeof events, string> = {
  task_assigned: "وظیفه‌ای به شما واگذار شد",
  task_reminder: "یادآور وظیفه",
  task_updated: "یکی از وظایف شما به‌روز شد",
  comment_mentioned: "در دیدگاهی به شما اشاره شد",
  comment_replied: "به دیدگاه شما پاسخ داده شد",
  workspace_invited: "دعوت تازه‌ای برای یک فضای کاری دارید",
  workspace_role_changed: "نقش شما در فضای کاری تغییر کرد",
  project_member_added: "به پروژه‌ای اضافه شدید",
  project_role_changed: "نقش شما در پروژه تغییر کرد",
};

const persianRoles: Readonly<Record<string, string>> = {
  owner: "مالک", admin: "مدیر", member: "عضو", manager: "مدیر پروژه", viewer: "بیننده",
};

export function notificationContent(notification: InboxNotification, locale: Locale = "en") {
  const [englishTitle, icon, tone] = events[notification.event_type] ??
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

  const roles = [payload.old_role, payload.new_role].filter(Boolean);
  if (roles.length === 0 && payload.role) roles.push(payload.role);
  const role = locale === "fa"
    ? roles.map((value) => {
      const key = String(value).toLowerCase();
      return Object.hasOwn(persianRoles, key) ? persianRoles[key] : value;
    }).join(" ← ")
    : roles.join(" → ");
  return {
    title: locale === "fa" ? persianTitles[notification.event_type] ?? "فعالیت تازه" : englishTitle,
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
