"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import AuthShell from "@/components/auth/AuthShell";
import Button from "@/components/ui/Button";
import { getAiCallback, getAiConsentInteraction } from "@/lib/ai-consent";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLocale } from "@/lib/preferences";
import styles from "./page.module.css";

const endpoint = "/api/v1/ai/consent/";

type Review = { client_name: string; account_email: string; scopes: string[]; callback: string };
type ReviewState = { interaction: string; userId: number; review: Review | null };

function subscribe(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

export default function AiConsentPage() {
  const { t } = useLocale();
  const { accessToken, user, isLoading, sessionUnavailable, retrySession } = useAuth();
  const interaction = useSyncExternalStore(
    subscribe, () => getAiConsentInteraction(window.location.hash), () => undefined,
  );
  const [state, setState] = useState<ReviewState | null>(null);
  const [decisionError, setDecisionError] = useState(false);
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const userId = user?.id;

  useEffect(() => {
    if (!interaction || !accessToken || userId === undefined) return;
    const controller = new AbortController();
    apiFetch<Review>(endpoint, {
      token: accessToken, headers: { "X-TeamBoard-AI-Interaction": interaction },
      signal: controller.signal, timeoutMs: 10_000, cache: "no-store",
    }).then(
      (review) => {
        if (!controller.signal.aborted) setState({ interaction, userId, review });
      },
      () => {
        if (!controller.signal.aborted) setState({ interaction, userId, review: null });
      },
    );
    return () => controller.abort();
  }, [accessToken, interaction, userId]);

  async function decide(allow: boolean) {
    if (!accessToken || !interaction || !review || inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setDecisionError(false);
    try {
      const result = await apiFetch<{ redirect_url: string }>(endpoint, {
        method: "POST", token: accessToken, timeoutMs: 10_000,
        headers: { "X-TeamBoard-AI-Interaction": interaction },
        body: JSON.stringify({ allow }),
      });
      const redirect = getAiCallback(result.redirect_url, review.callback);
      if (!redirect) throw new Error("Invalid client callback");
      window.location.replace(redirect);
    } catch {
      setDecisionError(true);
      inFlight.current = false;
      setPending(false);
    }
  }

  const current = state?.interaction === interaction && state?.userId === userId ? state : null;
  const review = current?.review;
  const writeAccess = review?.scopes.includes("teamboard.write");
  const sensitiveAccess = review?.scopes.includes("teamboard.sensitive");

  return (
    <AuthShell>
      <section className={styles.panel}>
        <h1>{t("Connect an AI client", "اتصال برنامهٔ هوش مصنوعی")}</h1>
        {isLoading || interaction === undefined ? (
          <p role="status">{t("Restoring your session…", "در حال بازیابی نشست…")}</p>
        ) : sessionUnavailable ? (
          <div>
            <p role="alert">{t("Could not restore your session.", "بازیابی نشست انجام نشد.")}</p>
            <Button type="button" className={styles.secondary} onClick={retrySession}>{t("Try again", "تلاش دوباره")}</Button>
          </div>
        ) : !interaction || (current && !review) ? (
          <p role="alert">{t("This request is unavailable. Start a new connection from your AI client.", "این درخواست در دسترس نیست. اتصال تازه‌ای را از برنامهٔ هوش مصنوعی آغاز کنید.")}</p>
        ) : !accessToken ? (
          <Link className={styles.primary} href={`/login#ai=${interaction}`} prefetch={false}>{t("Sign in to review", "ورود برای بررسی درخواست")}</Link>
        ) : !review ? (
          <p role="status">{t("Loading connection request…", "در حال بارگیری درخواست اتصال…")}</p>
        ) : (
          <>
            <p>{t("Review the access you are about to grant.", "دسترسی درخواستی را پیش از تأیید بررسی کنید.")}</p>
            <dl className={styles.details}>
              <dt>{t("AI client", "برنامهٔ هوش مصنوعی")}</dt><dd><bdi>{review.client_name}</bdi></dd>
              <dt>{t("TeamBoard account", "حساب تیم‌برد")}</dt><dd><bdi>{review.account_email}</bdi></dd>
              <dt>{t("Access", "دسترسی")}</dt><dd>
                <p>{t("Read records you can access in TeamBoard.", "مشاهدهٔ داده‌هایی که در تیم‌برد به آن‌ها دسترسی دارید.")}</p>
                {writeAccess && <p>{t("Create and edit records you can manage in TeamBoard.", "ایجاد و ویرایش داده‌هایی که در تیم‌برد مجوز مدیریت آن‌ها را دارید.")}</p>}
                {sensitiveAccess && <p>{t("Request actions that need your explicit approval in TeamBoard.", "درخواست عملیات حساسی که به تأیید صریح شما در تیم‌برد نیاز دارند.")}</p>}
              </dd>
            </dl>
            {decisionError && <p role="alert">{t("The request could not be completed. Check the AI client or start again.", "درخواست تکمیل نشد. برنامهٔ هوش مصنوعی را بررسی کنید یا دوباره شروع کنید.")}</p>}
            <div className={styles.actions}>
              <Button type="button" className={styles.primary} disabled={pending} onClick={() => void decide(true)}>{writeAccess ? t("Allow read and write access", "تأیید دسترسی خواندن و نوشتن") : t("Allow read access", "تأیید دسترسی خواندن")}</Button>
              <Button type="button" className={styles.secondary} disabled={pending} onClick={() => void decide(false)}>{t("Deny", "رد درخواست")}</Button>
            </div>
          </>
        )}
      </section>
    </AuthShell>
  );
}
