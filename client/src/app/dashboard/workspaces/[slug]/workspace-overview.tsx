
"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useWorkspace } from "./workspace-context";
import styles from "./workspace-detail.module.css";

export default function WorkspaceOverview() {
  const { ui, formatDate } = useWorkspaceLocale();
  const workspace = useWorkspace();

  const createdDate = formatDate(workspace.created_at, { month: "short", day: "2-digit", year: "numeric" });

  const role = workspace.role
    ? workspace.role.charAt(0).toUpperCase() +
      workspace.role.slice(1)
    : "Unknown";

  return (
    <section className={styles.infoCard}>
      <h2>{ui("Workspace overview")}</h2>

      <dl className={styles.details}>
        <div>
          <dt>{ui("Workspace name")}</dt>
          <dd>{workspace.name}</dd>
        </div>

        <div>
          <dt>{ui("Your role")}</dt>
          <dd><span data-role-tone={workspace.role}>{ui(role)}</span></dd>
        </div>

        <div>
          <dt>{ui("Created")}</dt>
          <dd>{createdDate}</dd>
        </div>

        <div>
          <dt>{ui("Workspace ID")}</dt>
          <dd>{workspace.id}</dd>
        </div>
      </dl>
    </section>
  );
}
