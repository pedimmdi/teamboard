
"use client";

import { useWorkspace } from "./workspace-context";
import styles from "./workspace-detail.module.css";

export default function WorkspacePage() {
  const workspace = useWorkspace();

  const createdDate = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(workspace.created_at));

  const role = workspace.role
    ? workspace.role.charAt(0).toUpperCase() +
      workspace.role.slice(1)
    : "Unknown";

  return (
    <section className={styles.infoCard}>
      <h2>Workspace overview</h2>

      <dl className={styles.details}>
        <div>
          <dt>Workspace name</dt>
          <dd>{workspace.name}</dd>
        </div>

        <div>
          <dt>Your role</dt>
          <dd>{role}</dd>
        </div>

        <div>
          <dt>Created</dt>
          <dd>{createdDate}</dd>
        </div>

        <div>
          <dt>Workspace ID</dt>
          <dd>{workspace.id}</dd>
        </div>
      </dl>
    </section>
  );
}
