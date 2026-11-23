"use client";

import { useSyncExternalStore } from "react";
import { direction, LOCALE_COOKIE, parseLocale, parseTheme, publicLocale, THEME_COOKIE, type Locale, type Theme } from "@/lib/locale";
import { BoundaryError } from "@/components/route-feedback";
import "./globals.css";

export default function GlobalError({ retry, reset }: { retry?: () => void; reset?: () => void }) {
  const appearance = useSyncExternalStore(subscribe, browserAppearance, () => "en:light" as const);
  const [locale, theme] = appearance.split(":") as [Locale, Theme];
  return (
    <html lang={locale} dir={direction(locale)} data-theme={theme}>
      <body>
        <main><BoundaryError retry={retry} reset={reset} language={locale} /></main>
      </body>
    </html>
  );
}

function subscribe() {
  return () => {};
}

function browserAppearance(): `${Locale}:${Theme}` {
  const cookies = new URLSearchParams(document.cookie.split(/;\s*/).join("&"));
  const locale = publicLocale(location.pathname) ?? parseLocale(cookies.get(LOCALE_COOKIE));
  return `${locale}:${parseTheme(cookies.get(THEME_COOKIE))}`;
}
