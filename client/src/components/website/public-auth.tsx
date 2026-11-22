"use client";

import Link from "next/link";
import { useEffect, type ComponentProps } from "react";
import { useRouter } from "next/navigation";
import styles from "@/app/(public)/website.module.css";
import { useAuth } from "@/lib/auth";
import { usePreferences } from "@/lib/preferences";
import type { WebsiteLocale } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";

export function HomeSession({ locale }: { locale: WebsiteLocale }) {
  const { isLoading, isAuthenticated } = useAuth();
  const { setLocale } = usePreferences();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      if (locale === "fa") setLocale(locale);
      router.replace("/dashboard");
    }
  }, [isLoading, isAuthenticated, locale, router, setLocale]);
  return null;
}

export function AuthEntry({ locale, ...props }: ComponentProps<typeof Link> & { locale: WebsiteLocale }) {
  const { setLocale } = usePreferences();
  return <Link {...props} prefetch={false} onClick={() => setLocale(locale)} />;
}

export function PublicAuth({ locale }: { locale: WebsiteLocale }) {
  const { isAuthenticated, isLoading } = useAuth();
  const copy = websiteCopy[locale];
  return (
    <div className={styles.auth}>
      {isAuthenticated ? (
        <AuthEntry locale={locale} href="/dashboard" className={styles.primary}>{copy.dashboard}</AuthEntry>
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
