"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { useLocale, type Locale } from "@/lib/preferences";
import styles from "./route-feedback.module.css";

export function RouteLoading({ label }: { label?: string }) {
  const { t } = useLocale();
  return (
    <section className={styles.loading}>
      <p role="status">{label ?? t("Loading…", "در حال بارگیری…")}</p>
      <div className={styles.skeleton} aria-hidden="true"><i /><i /><i /></div>
    </section>
  );
}

export function RouteFeedback({ title, description, onRetry, children, language }: {
  title: string;
  description: string;
  onRetry?: () => void;
  children?: ReactNode;
  language?: Locale;
}) {
  const { locale } = useLocale();
  const persian = (language ?? locale) === "fa";
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  return (
    <section className={styles.feedback}>
      <h1 tabIndex={-1} ref={heading}>{title}</h1>
      <p>{description}</p>
      <div className={styles.actions}>
        {onRetry && <button type="button" onClick={onRetry}>{persian ? "تلاش دوباره" : "Try again"}</button>}
        <Link href={persian ? "/fa" : "/"}>{persian ? "رفتن به خانه" : "Go to home"}</Link>
        {children}
      </div>
    </section>
  );
}

export function BoundaryError({ retry, reset, language }: { retry?: () => void; reset?: () => void; language?: Locale }) {
  const { locale } = useLocale();
  const persian = (language ?? locale) === "fa";
  return (
    <RouteFeedback
      language={language}
      title={persian ? "این صفحه نمایش داده نشد" : "This page couldn’t be displayed"}
      description={persian ? "دوباره این صفحه را باز کنید یا به صفحهٔ خانه برگردید." : "Try opening the page again. You can also return to the home page."}
      onRetry={retry ?? reset ?? (() => window.location.reload())}
    />
  );
}
