"use client";

import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { direction, LOCALE_COOKIE, publicLocale, regionalLocale, THEME_COOKIE, type Locale, type Theme } from "./locale";

export type { Locale, Theme } from "./locale";

const PreferencesContext = createContext({
  locale: "en" as Locale,
  theme: "light" as Theme,
  setLocale: (_locale: Locale) => { void _locale; },
  setTheme: (_theme: Theme) => { void _theme; },
});

function writePreference(name: string, value: string) {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export function persistLocale(locale: Locale) {
  writePreference(LOCALE_COOKIE, locale);
}

export function PreferencesProvider({
  initialLocale, preferredLocale, initialTheme, children,
}: {
  initialLocale: Locale;
  preferredLocale: Locale;
  initialTheme: Theme;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [selectedLocale, setSelectedLocale] = useState(preferredLocale);
  const [theme, setSelectedTheme] = useState(initialTheme);
  const locale = pathname ? publicLocale(pathname) ?? selectedLocale : initialLocale;

  useLayoutEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = direction(locale);
    document.documentElement.dataset.theme = theme;
  }, [initialLocale, initialTheme, locale, theme]);

  const setLocale = useCallback((next: Locale) => {
    persistLocale(next);
    setSelectedLocale(next);
  }, []);
  const setTheme = useCallback((next: Theme) => {
    writePreference(THEME_COOKIE, next);
    setSelectedTheme(next);
  }, []);
  const value = useMemo(() => ({ locale, theme, setLocale, setTheme }), [locale, theme, setLocale, setTheme]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function useLocale() {
  const { locale } = useContext(PreferencesContext);
  return useMemo(() => {
    const region = regionalLocale(locale);
    return {
      locale,
      t: (english: string, persian: string) => locale === "fa" ? persian : english,
      formatDate: (value: string | number | Date, options?: Intl.DateTimeFormatOptions) => {
        const date = value instanceof Date ? value : new Date(value);
        return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat(region, {
          ...(/^\d{4}-\d{2}-\d{2}$/.test(String(value)) ? { timeZone: "UTC" } : {}),
          ...options,
        }).format(date);
      },
      formatNumber: (value: number, options?: Intl.NumberFormatOptions) => new Intl.NumberFormat(region, options).format(value),
    };
  }, [locale]);
}

export function usePreferences() {
  return useContext(PreferencesContext);
}
