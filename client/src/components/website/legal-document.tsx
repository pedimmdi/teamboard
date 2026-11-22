import Link from "next/link";
import { getLocale } from "@/lib/server-preferences";
import { publicMetadata, websitePath } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import styles from "@/app/(public)/website.module.css";

type LegalPage = "privacy" | "terms";

export async function legalMetadata(page: LegalPage) {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return publicMetadata(copy[`${page}Title`], copy[`${page}Description`], `/${page}`, locale);
}

export async function LegalDocument({ page }: { page: LegalPage }) {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return (
    <article className={styles.document}>
      <header className={styles.documentHeading}>
        <h1>{copy[`${page}Title`]}</h1>
        <p>{copy[`${page}Description`]}</p>
      </header>
      {copy[`${page}Sections`].map(([title, body]) => <section key={title}><h2>{title}</h2><p>{body}</p></section>)}
      <Link className={styles.textLink} href={websitePath(page === "privacy" ? "/contact" : "/privacy", locale)}>{page === "privacy" ? copy.contact : copy.privacy}</Link>
    </article>
  );
}
