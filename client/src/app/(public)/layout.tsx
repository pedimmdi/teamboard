import Link from "next/link";
import { PublicAuth } from "@/components/website/public-auth";
import BrandMark from "@/components/ui/BrandMark";
import { WebsitePreferences } from "@/components/website/website-preferences";
import { getLocale } from "@/lib/server-preferences";
import { websitePath } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import styles from "./website.module.css";

const primaryLinks = ["about", "blog", "contact"] as const;
const footerLinks = [...primaryLinks, "privacy", "terms"] as const;

export default async function PublicLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  const brand = (
    <Link href={websitePath("/", locale)} className={styles.brand}>
      <span className={styles.mark}><BrandMark /></span>
      <span>{locale === "fa" ? "تیم‌برد" : "TeamBoard"}</span>
    </Link>
  );

  return (
    <div className={styles.site}>
      <a className={styles.skip} href="#public-content">{copy.skip}</a>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          {brand}
          <nav className={styles.nav} aria-label={copy.nav}>
            {primaryLinks.map((page) => <Link key={page} href={websitePath(`/${page}`, locale)}>{copy[page]}</Link>)}
          </nav>
          <div className={styles.headerActions}>
            <WebsitePreferences locale={locale} />
            <PublicAuth locale={locale} />
          </div>
        </div>
      </header>
      <main id="public-content">{children}</main>
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div>
            {brand}
            <p>{copy.tagline}</p>
          </div>
          <nav aria-label={copy.footerNav}>
            {footerLinks.map((page) => <Link key={page} href={websitePath(`/${page}`, locale)}>{copy[page]}</Link>)}
          </nav>
          <small>© {new Intl.NumberFormat(locale, { useGrouping: false }).format(new Date().getUTCFullYear())} <bdi>TeamBoard</bdi></small>
        </div>
      </footer>
    </div>
  );
}
