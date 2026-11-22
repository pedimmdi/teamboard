"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/preferences";
import { dashboardWorkspaceKey, loadDashboardWorkspace } from "./dashboard-workspace";
import styles from "./dashboard.module.css";

export default function DashboardEntry() {
  const { t } = useLocale();
  const { accessToken, user } = useAuth();
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!accessToken || !user) return;
    let cancelled = false;
    let saved: string | null = null;
    try {
      const key = dashboardWorkspaceKey(user.id);
      saved = localStorage.getItem(key) || sessionStorage.getItem(key);
    } catch {}

    loadDashboardWorkspace(accessToken, undefined, saved).then((workspace) => {
      if (cancelled) return;
      router.replace(workspace
        ? `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/dashboard`
        : "/dashboard/workspaces");
    }).catch(() => {
      if (!cancelled) setFailed(true);
    });
    return () => { cancelled = true; };
  }, [accessToken, user, router, retry]);

  return (
    <div className={styles.entry}>
      {failed ? (
        <>
          <p role="alert">{t("Unable to select your workspace.", "انتخاب فضای کاری انجام نشد.")}</p>
          <button type="button" className={styles.secondaryButton} onClick={() => {
            setFailed(false);
            setRetry((value) => value + 1);
          }}>{t("Try again", "تلاش دوباره")}</button>
        </>
      ) : (
        <p role="status">{t("Opening your dashboard…", "در حال باز کردن داشبورد…")}</p>
      )}
    </div>
  );
}
