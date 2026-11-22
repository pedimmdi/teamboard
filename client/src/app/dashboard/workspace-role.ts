import type { Workspace } from "@/lib/api";
import type { Locale } from "@/lib/locale";

const roleLabels = {
  en: { owner: "Owner", admin: "Admin", member: "Member", unknown: "Unknown" },
  fa: { owner: "مالک", admin: "مدیر", member: "عضو", unknown: "نامشخص" },
};

export function workspaceRoleLabel(role: Workspace["role"], locale: Locale) {
  return roleLabels[locale][role ?? "unknown"];
}
