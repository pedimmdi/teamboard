export type Locale = "en" | "fa";
export type Theme = "light" | "dark";

export const LOCALE_COOKIE = "teamboard-locale";
export const THEME_COOKIE = "teamboard-theme";
export const LOCALE_HEADER = "x-teamboard-locale";

export function parseLocale(value?: string | null): Locale {
  return value === "fa" ? "fa" : "en";
}

export function parseTheme(value?: string | null): Theme {
  return value === "dark" ? "dark" : "light";
}

export function publicLocale(pathname: string): Locale | undefined {
  if (pathname === "/fa" || pathname.startsWith("/fa/")) return "fa";
  if (/^\/(?:about\/?|contact\/?|privacy\/?|terms\/?|blog(?:\/.*)?)?$/.test(pathname)) return "en";
}

export function direction(locale: Locale) {
  return locale === "fa" ? "rtl" : "ltr";
}

export function regionalLocale(locale: Locale) {
  return locale === "fa" ? "fa-IR" : "en-US";
}
