import type { ProjectRole, WorkspaceRole } from "@/lib/api";

export function projectRoleLabel(role: ProjectRole | null) {
  return role === "manager"
    ? "Manager"
    : role === "member"
      ? "Member"
      : "Admin access";
}

export function formatProjectDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export function projectPermissions(
  workspaceRole: WorkspaceRole | null,
  projectRole: ProjectRole | null,
) {
  const admin = workspaceRole === "owner" || workspaceRole === "admin";
  return {
    canCreate: admin,
    canManage: admin || (workspaceRole !== null && projectRole === "manager"),
    canAssignManagers: admin,
    canDelete: admin,
    canLeave: workspaceRole !== null && projectRole !== null,
  };
}
