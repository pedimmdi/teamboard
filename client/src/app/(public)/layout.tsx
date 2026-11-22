import Link from "next/link";
import { PublicAuth } from "@/components/website/public-auth";
import styles from "./website.module.css";
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className={styles.site}>
      <a className={styles.skip} href="#public-content">
        Skip to content
      </a>
      <header className={styles.header}>
        <Link href="/" className={styles.brand}>
          <span aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <rect x="3" y="7" width="3" height="10" rx="1" />
              <rect x="8.5" y="3" width="3" height="14" rx="1" />
              <rect x="14" y="5" width="3" height="12" rx="1" />
            </svg>
          </span>{" "}
          TeamBoard
        </Link>
        <nav aria-label="Main navigation">
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/contact">Contact</Link>
        </nav>
        <div className={styles.auth}>
          <PublicAuth />
        </div>
      </header>
      <main id="public-content">{children}</main>
      <footer className={styles.footer}>
        <div>
          <Link href="/" className={styles.brand}>
            TeamBoard
          </Link>
          <p>A shared place for work that moves forward.</p>
        </div>
        <nav aria-label="Footer navigation">
          <Link href="/about">About</Link>
          <Link href="/contact">Contact</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </nav>
        <small>© {new Date().getUTCFullYear()} TeamBoard</small>
      </footer>
    </div>
  );
}
