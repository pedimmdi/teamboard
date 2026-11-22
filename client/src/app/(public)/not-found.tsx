import Link from "next/link";
import { getLocale } from "@/lib/server-preferences";
import { websitePath } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import styles from "./website.module.css";

export default async function PublicNotFound() {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return (
    <section className={`${styles.document} ${styles.messagePage}`}>
      <h1>{new Intl.NumberFormat(locale, { useGrouping: false }).format(404)}</h1>
      <p>{copy.notFound}</p>
      <Link className={styles.primary} href={websitePath("/", locale)}>{copy.home}</Link>
    </section>
  );
}
