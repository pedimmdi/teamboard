"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import styles from "@/app/(public)/website.module.css";
import { useAuth } from "@/lib/auth";
import { usePreferences } from "@/lib/preferences";
import type { WebsiteLocale } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";

const panelLabel = (locale: WebsiteLocale) => locale === "fa" ? "ورود به پنل" : websiteCopy[locale].dashboard;

export function AuthEntry({ locale, ...props }: ComponentProps<typeof Link> & { locale: WebsiteLocale }) {
  const { setLocale } = usePreferences();
  return <Link {...props} prefetch={false} onClick={() => setLocale(locale)} />;
}

export function PublicStart({ locale, children }: { locale: WebsiteLocale; children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  return (
    <AuthEntry locale={locale} className={styles.primary} href={isAuthenticated ? "/dashboard" : "/register"}>
      {isAuthenticated ? panelLabel(locale) : children}
    </AuthEntry>
  );
}

export function PublicAuth({ locale }: { locale: WebsiteLocale }) {
  const { isAuthenticated, isLoading } = useAuth();
  const copy = websiteCopy[locale];
  return (
    <div className={styles.auth}>
      {isAuthenticated ? (
        <AuthEntry locale={locale} href="/dashboard" className={styles.primary}>
          {panelLabel(locale)}
        </AuthEntry>
      ) : (
        <>
          <AuthEntry locale={locale} href="/login" className={styles.login}>{copy.login}</AuthEntry>
          <AuthEntry locale={locale} href="/register" className={styles.primary}>{copy.register}</AuthEntry>
          {isLoading && <span className={styles.srOnly} role="status">{copy.checking}</span>}
        </>
      )}
    </div>
  );
}
