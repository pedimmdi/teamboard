"use client";

import { useRouter } from "next/navigation";
import { useLocale, usePreferences } from "@/lib/preferences";
import styles from "./preferences-controls.module.css";

export function PreferencesControls({ alternateHref, compact = false }: {
  alternateHref?: string;
  compact?: boolean;
}) {
  const router = useRouter();
  const { locale, t } = useLocale();
  const { theme, setLocale, setTheme } = usePreferences();
  const nextLocale = locale === "fa" ? "en" : "fa";
  const languageLabel = t("Switch to Persian", "تغییر زبان به انگلیسی");
  const themeLabel = t("Dark mode", "حالت تیره");
  const languageName = nextLocale === "fa" ? "فارسی" : "English";

  function changeLocale() {
    setLocale(nextLocale);
    router.refresh();
  }

  return (
    <div className={styles.controls} role="group" aria-label={t("Appearance and language", "ظاهر و زبان")}>
      {alternateHref ? (
        <a className={styles.button} href={alternateHref} hrefLang={nextLocale}
          aria-label={languageLabel} onClick={() => setLocale(nextLocale)}>
          <span lang={nextLocale}>{languageName}</span>
        </a>
      ) : (
        <button type="button" className={styles.button} onClick={changeLocale} aria-label={languageLabel}>
          <span lang={nextLocale}>{languageName}</span>
        </button>
      )}
      <button type="button" className={styles.button} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        aria-label={themeLabel} title={themeLabel} aria-pressed={theme === "dark"}>
        <span className={theme === "dark" ? styles.sun : styles.moon} aria-hidden="true" />
        {!compact && <span aria-hidden="true">{t("Theme", "تم")}</span>}
      </button>
    </div>
  );
}
