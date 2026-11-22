"use client";

import { useLocale } from "@/lib/preferences";
import { websiteCopy } from "@/lib/website-copy";
import styles from "./website.module.css";

export default function WebsiteError({ reset }: { reset: () => void }) {
  const { locale } = useLocale();
  const copy = websiteCopy[locale];
  return (
    <section className={`${styles.document} ${styles.messagePage}`} role="alert">
      <h1>{copy.errorTitle}</h1>
      <p>{copy.errorBody}</p>
      <button className={styles.primary} type="button" onClick={reset}>{copy.retry}</button>
    </section>
  );
}
