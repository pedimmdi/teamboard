"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RouteFeedback, RouteLoading } from "@/components/route-feedback";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/preferences";
import { dashboardWorkspaceKey, loadDashboardWorkspace } from "./dashboard-workspace";

export default function DashboardEntry() {
  const { t } = useLocale();
  const { accessToken, user } = useAuth();
  const userId = user?.id;
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!accessToken || userId === undefined) return;
    let cancelled = false;
    const deadline = window.setTimeout(() => {
      cancelled = true;
      setFailed(true);
    }, 22_000);
    let saved: string | null = null;
    try {
      const key = dashboardWorkspaceKey(userId);
      saved = localStorage.getItem(key) || sessionStorage.getItem(key);
    } catch {}

    loadDashboardWorkspace(accessToken, undefined, saved).then((workspace) => {
      if (cancelled) return;
      router.replace(workspace
        ? `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/dashboard`
        : "/dashboard/workspaces");
    }).catch(() => {
      window.clearTimeout(deadline);
      if (!cancelled) setFailed(true);
    });
    return () => {
      cancelled = true;
      window.clearTimeout(deadline);
    };
  }, [accessToken, userId, router, retry]);

  if (!failed) return <RouteLoading label={t("Opening your dashboard…", "در حال باز کردن داشبورد…")} />;

  return (
    <RouteFeedback
      title={t("Unable to select your workspace", "فضای کاری باز نشد")}
      description={t("Try again to resume where you left off, or open your workspace list.", "برای ادامهٔ کار دوباره تلاش کنید یا فهرست فضاهای کاری را باز کنید.")}
      onRetry={() => {
        setFailed(false);
        setRetry((value) => value + 1);
      }}
    >
      <Link href="/dashboard/workspaces">{t("View workspaces", "دیدن فضاهای کاری")}</Link>
    </RouteFeedback>
  );
}
