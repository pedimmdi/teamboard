
"use client";

import { useOrganization } from "./organization-context";
import styles from "./organization-detail.module.css";

export default function OrganizationPage() {
  const organization = useOrganization();

  const createdDate = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(organization.created_at));

  const role = organization.role
    ? organization.role.charAt(0).toUpperCase() +
      organization.role.slice(1)
    : "Unknown";

  return (
    <section className={styles.infoCard}>
      <h2>Organization overview</h2>

      <dl className={styles.details}>
        <div>
          <dt>Organization name</dt>
          <dd>{organization.name}</dd>
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
          <dt>Organization ID</dt>
          <dd>{organization.id}</dd>
        </div>
      </dl>
    </section>
  );
}
