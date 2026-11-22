import { cookies, headers } from "next/headers";
import { LOCALE_COOKIE, LOCALE_HEADER, THEME_COOKIE, parseLocale, parseTheme } from "./locale";

export async function getPreferences() {
  const [cookieStore, requestHeaders] = await Promise.all([cookies(), headers()]);
  const preferredLocale = parseLocale(cookieStore.get(LOCALE_COOKIE)?.value);
  const routeLocale = requestHeaders.get(LOCALE_HEADER);

  return {
    locale: routeLocale === "fa" || routeLocale === "en" ? routeLocale : preferredLocale,
    preferredLocale,
    theme: parseTheme(cookieStore.get(THEME_COOKIE)?.value),
  };
}

export async function getLocale() {
  return (await getPreferences()).locale;
}
