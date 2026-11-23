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
        <div className={styles.formNav}>
          <Link className={styles.homeLink} href={locale === "fa" ? "/fa" : "/"}>
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" width="18" height="18">
              <path d="m3 9 7-6 7 6v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <path d="M8 17v-5h4v5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
            {t("Home", "خانه")}
          </Link>
          <PreferencesControls compact />
        </div>
        <div className={styles.formContainer}>{children}</div>
      </section>
    </main>
  );
}
