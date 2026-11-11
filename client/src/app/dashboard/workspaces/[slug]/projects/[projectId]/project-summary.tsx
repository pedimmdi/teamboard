import { useState } from "react";
import Link from "next/link";
import Avatar from "@/components/ui/Avatar";
import type { ProjectMember } from "@/lib/api";
import styles from "../projects.module.css";

export default function ProjectSummary({
  description,
  membersHref,
  members,
  membersLoading,
  membersError,
  onRetryMembers,
}: {
  description: string;
  membersHref: string;
  members: ProjectMember[];
  membersLoading: boolean;
  membersError: string;
  onRetryMembers: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const characters = Array.from(description);
  const truncated = characters.length > 240;
  const managers = members.filter((member) => member.role === "manager").length;

  return (
    <div className={styles.overviewGrid}>
      <section className={`${styles.card} ${styles.summaryCard}`}>
        <h2>About</h2>
        <p className={styles.aboutText}>
          {truncated && !expanded
            ? `${characters.slice(0, 240).join("").trimEnd()}…`
            : description || "No description has been added yet."}
        </p>
        {truncated && (
          <button
            type="button"
            className={styles.summaryLink}
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Show less" : "Read more"}
          </button>
        )}
      </section>
      <section className={`${styles.card} ${styles.summaryCard}`}>
        <div className={styles.header}>
          <h2>Team</h2>
          <Link className={styles.summaryLink} href={membersHref}>
            View members
          </Link>
        </div>
        {membersLoading ? (
          <p className={styles.muted} role="status">Loading team…</p>
        ) : membersError ? (
          <>
            <p className={styles.error} role="alert">{membersError}</p>
            <button type="button" className={styles.summaryLink} onClick={onRetryMembers}>
              Try again
            </button>
          </>
        ) : (
          <>
            <div className={styles.avatars}>
              {members.slice(0, 5).map((member) => (
                <span key={member.id} title={member.user_email}>
                  <Avatar
                    className={styles.avatar}
                    src={member.avatar}
                    fallback={member.user_email.charAt(0).toUpperCase()}
                    size={32}
                  />
                </span>
              ))}
            </div>
            <p className={styles.hint}>
              {members.length} {members.length === 1 ? "member" : "members"} ·{" "}
              {managers} {managers === 1 ? "manager" : "managers"}
            </p>
          </>
        )}
      </section>
    </div>
  );
}
