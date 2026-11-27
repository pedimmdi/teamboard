"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import AuthShell from "@/components/auth/AuthShell";
import Button from "@/components/ui/Button";
import { getTaskDeletionApproval } from "@/lib/ai-consent";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/preferences";
import styles from "../authorize/page.module.css";

type Review = { status: "pending" | "approved" | "denied"; task_id: string; task_title: string; expires_at: string };

function subscribe(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

export default function TaskDeletionApprovalPage() {
  const { t } = useLocale();
  const { accessToken, user, isLoading, sessionUnavailable, retrySession } = useAuth();
  const userId = user?.id;
  const approval = useSyncExternalStore(subscribe, () => getTaskDeletionApproval(window.location.hash), () => undefined);
  const [state, setState] = useState<{ id: string; user: number; value: Review | null }>();
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const endpoint = `/api/v1/ai/approvals/tasks/${approval}/`;

  useEffect(() => {
    if (!approval || !accessToken || userId === undefined) return;
    const controller = new AbortController();
    apiFetch<Review>(endpoint, { token: accessToken, signal: controller.signal, timeoutMs: 10_000 }).then(
      (value) => {
        if (!controller.signal.aborted) setState({ id: approval, user: userId, value });
      },
      () => {
        if (!controller.signal.aborted) setState({ id: approval, user: userId, value: null });
      },
    );
    return () => controller.abort();
  }, [accessToken, approval, endpoint, userId]);

  async function decide(approve: boolean) {
    if (!approval || !accessToken || userId === undefined || pending) return;
    setPending(true);
    setFailed(false);
    try {
      const value = await apiFetch<Review>(endpoint, {
        method: "POST", token: accessToken, timeoutMs: 10_000, body: JSON.stringify({ approve }),
      });
      setState({ id: approval, user: userId, value });
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  }

  const review = state && state.id === approval && state.user === userId ? state.value : undefined;
  const unavailable = t("This request expired or your access or the task changed. Ask the AI client for a new request.",
    "این درخواست منقضی شده یا دسترسی شما یا خود تسک تغییر کرده است. از برنامهٔ هوش مصنوعی درخواست تازه‌ای بخواهید.");

  return (
    <AuthShell>
      <section className={styles.panel}>
        <h1>{t("Review task deletion", "بررسی حذف کار")}</h1>
        {isLoading || approval === undefined ? <p role="status">{t("Restoring your session…", "در حال بازیابی نشست…")}</p>
          : sessionUnavailable ? <Button type="button" className={styles.secondary} onClick={retrySession}>{t("Retry session", "تلاش دوباره برای بازیابی نشست")}</Button>
          : !approval || review === null ? <p role="alert">{unavailable}</p>
          : !accessToken ? <Link className={styles.primary} href={`/login#approve-task=${approval}`} prefetch={false}>{t("Sign in to review", "ورود برای بررسی درخواست")}</Link>
          : !review ? <p role="status">{t("Loading request…", "در حال بارگیری درخواست…")}</p>
          : (
            <>
              <dl className={styles.details}>
                <dt>{t("Task", "کار")}</dt><dd><bdi>{review.task_title}</bdi></dd>
                <dt>{t("Task ID", "شناسهٔ کار")}</dt><dd><bdi>{review.task_id}</bdi></dd>
              </dl>
              {review.status === "approved" ? <p role="status">{t("Task deleted.", "کار حذف شد.")}</p>
                : review.status === "denied" ? <p role="status">{t("Request denied.", "درخواست رد شد.")}</p>
                : (
                  <>
                    <p>{t("Deleting this task permanently removes its comments and reminders.", "حذف کار، نظرات و یادآورهای آن را هم برای همیشه پاک می‌کند.")}</p>
                    {failed && <p role="alert">{unavailable}</p>}
                    <div className={styles.actions}>
                      <Button type="button" className={styles.secondary} disabled={pending} onClick={() => void decide(false)}>{t("Deny request", "رد درخواست")}</Button>
                      <Button type="button" className={styles.primary} disabled={pending} onClick={() => void decide(true)}>{t("Delete this task", "حذف این کار")}</Button>
                    </div>
                  </>
                )}
            </>
          )}
      </section>
    </AuthShell>
  );
}
