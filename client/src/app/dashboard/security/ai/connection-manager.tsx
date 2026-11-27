"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/preferences";
import styles from "../../dashboard.module.css";
import connectionStyles from "./connection-manager.module.css";

type Connection = { id: number; name: string; scopes: string[]; current_grant_at: string };
type ConnectionPage = { results: Connection[]; next_page: number | null };
const base = "/api/v1/ai/connections/";

export default function ConnectionManager() {
  const { locale, t } = useLocale();
  const { accessToken } = useAuth();
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [load, setLoad] = useState<{ token: string; key: string; data: ConnectionPage | null }>();
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<"success" | "failure">();
  const key = `${page}:${revision}`;

  useEffect(() => {
    if (!accessToken) return;
    const controller = new AbortController();
    const options = { token: accessToken, signal: controller.signal, timeoutMs: 10_000 };
    apiFetch<ConnectionPage>(`${base}?page=${page}`, options).then(
      (data) => {
        if (!controller.signal.aborted) setLoad({ token: accessToken, key, data });
      },
      () => {
        if (!controller.signal.aborted) setLoad({ token: accessToken, key, data: null });
      },
    );
    return () => controller.abort();
  }, [accessToken, key, page]);

  async function revoke(id?: number) {
    if (!accessToken || pending || !window.confirm(id === undefined
      ? t("Revoke all AI connections for this account?", "دسترسی همه اتصال‌های هوش مصنوعی این حساب لغو شود؟")
      : t("Revoke access for this AI connection?", "دسترسی این اتصال هوش مصنوعی لغو شود؟"))) return;
    setPending(true);
    setNotice(undefined);
    try {
      await apiFetch(`${base}${id === undefined ? "" : `${id}/`}revoke/`, {
        token: accessToken, method: "POST", timeoutMs: 10_000,
      });
      setPage(1);
      setRevision((current) => current + 1);
      setNotice("success");
    } catch {
      setNotice("failure");
    } finally {
      setPending(false);
    }
  }

  const data = load?.token === accessToken && load?.key === key ? load.data : undefined;
  const dateFormat = new Intl.DateTimeFormat(locale === "fa" ? "fa-IR-u-ca-persian" : "en", {
    dateStyle: "medium", timeStyle: "short", ...(locale === "fa" ? { timeZone: "Asia/Tehran" } : {}),
  });

  return (
    <section className={styles.page}>
      <div className={styles.content}>
        <header className={styles.pageHeader}>
          <div>
            <Link href="/dashboard/security">{t("Security", "امنیت")}</Link>
            <h1>{t("AI connections", "اتصال‌های هوش مصنوعی")}</h1>
            <p>{t("Review the clients that can access your account. Revocation applies immediately.", "برنامه‌های دارای دسترسی به حساب را بررسی کنید. لغو دسترسی بلافاصله اعمال می‌شود.")}</p>
          </div>
        </header>
        <div className={styles.card}>
          {notice === "success" && <p role="status">{t("Access revoked.", "دسترسی لغو شد.")}</p>}
          {notice === "failure" && <p role="alert">{t("Revocation failed. Try again.", "لغو دسترسی انجام نشد. دوباره تلاش کنید.")}</p>}
          {data === undefined && <p role="status">{t("Loading connections…", "در حال بارگیری اتصال‌ها…")}</p>}
          {data === null && <div className={connectionStyles.actions}>
            <p role="alert">{t("Connections could not be loaded.", "بارگیری اتصال‌ها انجام نشد.")}</p>
            <Button type="button" onClick={() => setRevision(revision + 1)}>{t("Try again", "تلاش دوباره")}</Button>
          </div>}
          {data?.results.length === 0 && <p>{t("You have no active AI connections.", "اتصال هوش مصنوعی فعالی ندارید.")}</p>}
          {!!data?.results.length && (
            <>
              <ul className={connectionStyles.list}>
                {data.results.map((connection) => (
                  <li key={connection.id} className={connectionStyles.row}>
                    <div>
                      <strong><bdi>{connection.name}</bdi></strong>
                      <p>{connection.scopes.includes("teamboard.write") ? t("Read and write access", "دسترسی خواندن و نوشتن") : t("Read access", "دسترسی خواندن")}</p>
                      <time dateTime={connection.current_grant_at}>{dateFormat.format(new Date(connection.current_grant_at))}</time>
                    </div>
                    <Button type="button" disabled={pending} onClick={() => void revoke(connection.id)}>
                      {t(`Revoke ${connection.name}`, `لغو دسترسی ${connection.name}`)}
                    </Button>
                  </li>
                ))}
              </ul>
              <div className={connectionStyles.actions}>
                <Button type="button" disabled={pending} onClick={() => void revoke()}>{t("Revoke all", "لغو همهٔ دسترسی‌ها")}</Button>
                {page > 1 && <Button type="button" onClick={() => setPage(page - 1)}>{t("Previous", "قبلی")}</Button>}
                {data.next_page && <Button type="button" onClick={() => setPage(data.next_page!)}>{t("Next", "بعدی")}</Button>}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
