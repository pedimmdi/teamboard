
"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { PreferencesControls } from "@/components/preferences-controls";
import BrandMark from "@/components/ui/BrandMark";
import { useLocale } from "@/lib/preferences";
import styles from "./VerificationShell.module.css";

type VerificationShellProps = {
  children: ReactNode;
};

export default function VerificationShell({
  children,
}: VerificationShellProps) {
  const { locale, t } = useLocale();
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <Link href={locale === "fa" ? "/fa" : "/"} className={styles.brand}>
            <span className={styles.brandMark}><BrandMark /></span>
            <span>{t("TeamBoard", "تیم‌برد")}</span>
          </Link>
          <PreferencesControls compact />
        </header>

        <section className={styles.card}>{children}</section>

      </div>
    </main>
  );
}
