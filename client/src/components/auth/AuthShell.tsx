"use client";

import { useLocale } from "@/lib/preferences";
import type { ReactNode } from "react";
import Link from "next/link";
import { PreferencesControls } from "@/components/preferences-controls";
import BrandMark from "@/components/ui/BrandMark";
import styles from "./AuthShell.module.css";

type AuthShellProps = {
  children: ReactNode;
};

export default function AuthShell({ children }: AuthShellProps) {
  const { locale, t } = useLocale();
  return (
    <main className={styles.layout}>
      <aside className={styles.brandPanel}>
        <Link href={locale === "fa" ? "/fa" : "/"} className={styles.logo}>
          <span className={styles.logoMark}><BrandMark /></span>
          <span>{t("TeamBoard", "تیم‌برد")}</span>
        </Link>

        <div className={styles.brandContent}>
          <p className={styles.tagline}>{t("Plan work. Ship together.", "کارها را برنامه‌ریزی کنید. با هم پیش ببرید.")}</p>
          <p>
            {t("One shared space for your team's projects, tasks, and progress.", "پروژه‌ها، وظایف و پیشرفت تیم‌تان را در یک فضای مشترک دنبال کنید.")}
          </p>

          <div className={styles.board} aria-hidden="true">
            {[t("To do", "در انتظار انجام"), t("In progress", "در حال انجام"), t("Done", "انجام‌شده")].map((column, index) => (
              <div className={styles.boardColumn} key={column}>
                <span className={styles.columnTitle}>{column}</span>
                <div className={styles.boardCard}>
                  <span className={styles.cardStatus} data-stage={index} />
                  <span>{[
                    t("Map the launch", "برنامه‌ریزی انتشار"),
                    t("Review the agenda", "مرور دستور جلسه"),
                    t("Share the brief", "ارسال شرح پروژه"),
                  ][index]}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

      </aside>

      <section className={styles.formPanel}>
        <div className={styles.preferences}><PreferencesControls compact /></div>
        <div className={styles.formContainer}>{children}</div>
      </section>
    </main>
  );
}
