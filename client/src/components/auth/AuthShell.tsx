
import type { ReactNode } from "react";
import Link from "next/link";
import styles from "./AuthShell.module.css";

type AuthShellProps = {
  children: ReactNode;
};

export default function AuthShell({ children }: AuthShellProps) {
  return (
    <main className={styles.layout}>
      <aside className={styles.brandPanel}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoMark}>T</span>
          <span>TeamBoard</span>
        </Link>

        <div className={styles.brandContent}>
          <h1>Plan work. Ship together.</h1>
          <p>
            One shared space for your team&apos;s projects,
            tasks, and progress.
          </p>

          <div className={styles.board} aria-hidden="true">
            {["To do", "In progress", "Done"].map((column, index) => (
              <div className={styles.boardColumn} key={column}>
                <span className={styles.columnTitle}>{column}</span>
                {Array.from({ length: index === 1 ? 2 : 3 }).map(
                  (_, cardIndex) => (
                    <div className={styles.boardCard} key={cardIndex}>
                      <span className={styles.cardLine} />
                      <span className={styles.cardLineShort} />
                    </div>
                  ),
                )}
              </div>
            ))}
          </div>
        </div>

        <span className={styles.copyright}>
          © {new Date().getFullYear()} TeamBoard
        </span>
      </aside>

      <section className={styles.formPanel}>
        <div className={styles.formContainer}>{children}</div>
      </section>
    </main>
  );
}
