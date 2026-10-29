
import type { ReactNode } from "react";
import styles from "./VerificationStatus.module.css";

type StatusTone = "info" | "success" | "error";

type VerificationStatusProps = {
  tone: StatusTone;
  title: string;
  description: ReactNode;
  children?: ReactNode;
};

export default function VerificationStatus({
  tone,
  title,
  description,
  children,
}: VerificationStatusProps) {
  return (
    <div className={styles.content}>
      <div className={`${styles.icon} ${styles[tone]}`}>
        {tone === "info" ? (
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="4" y="6" width="16" height="12" rx="2" />
            <path d="m5 8 7 5 7-5" />
          </svg>
        ) : tone === "success" ? (
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <path d="m8 12 2.5 2.5 5-5" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 8v5M12 16h.01" />
          </svg>
        )}
      </div>

      <h1>{title}</h1>
      <div className={styles.description}>{description}</div>

      {children && <div className={styles.actions}>{children}</div>}
    </div>
  );
}
