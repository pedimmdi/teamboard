
import type { ReactNode } from "react";
import Link from "next/link";
import styles from "./VerificationShell.module.css";

type VerificationShellProps = {
  children: ReactNode;
};

export default function VerificationShell({
  children,
}: VerificationShellProps) {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <Link href="/" className={styles.brand}>
          <span className={styles.brandMark}>T</span>
          <span>TeamBoard</span>
        </Link>

        <section className={styles.card}>{children}</section>

        <p className={styles.copyright}>
          © {new Date().getFullYear()} TeamBoard
        </p>
      </div>
    </main>
  );
}
