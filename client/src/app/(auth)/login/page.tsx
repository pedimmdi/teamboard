
"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AuthShell from "@/components/auth/AuthShell";
import PasswordField from "@/components/auth/PasswordField";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { ApiError, getCurrentUser, login } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  clearInvitationReturn,
  getInvitationAuthUrl,
  getSafeInvitationReturn,
  readInvitationReturn,
  saveInvitationReturn,
} from "@/lib/invitation-return";

import styles from "./login.module.css";

export default function LoginPage() {
  const { locale, t } = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { setTokens, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      const next = getSafeInvitationReturn(new URLSearchParams(window.location.search).get("next")) ?? readInvitationReturn();
      router.replace(next ?? "/dashboard");
    }
  }, [isLoading, isAuthenticated, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await login(email.trim(), password);
      const user = await getCurrentUser(data.access);

      setTokens(data.access, user);

      const params = new URLSearchParams(window.location.search);
      const returnPath =
        getSafeInvitationReturn(params.get("next")) ??
        readInvitationReturn();

      if (returnPath) {
        saveInvitationReturn(returnPath);
      } else {
        clearInvitationReturn();
      }

      router.replace(returnPath ?? "/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : t("Unable to sign in. Please try again.", "ورود انجام نشد. دوباره تلاش کنید."),
      );
    } finally {
      setLoading(false);
    }
  }

  function getRegisterPath() {
    const params = new URLSearchParams(window.location.search);
    const returnPath =
      getSafeInvitationReturn(params.get("next")) ??
      readInvitationReturn();

    if (returnPath) saveInvitationReturn(returnPath);

    return getInvitationAuthUrl("/register", returnPath);
  }

  if (isLoading || isAuthenticated) return (
    <AuthShell><p role="status">{t("Restoring your session…", "در حال بازیابی نشست شما…")}</p></AuthShell>
  );

  return (
    <AuthShell>
      <div className={styles.header}>
        <h1>{t("Welcome back", "خوش برگشتید")}</h1>
        <p>{t("Sign in to your TeamBoard account.", "وارد حساب تیم‌بورد خود شوید.")}</p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        {error && (
          <div className={styles.errorBanner} role="alert">
            <span aria-hidden="true">!</span>
            <p>{localizeAccountMessage(locale, error, "ورود انجام نشد. دوباره تلاش کنید.")}</p>
          </div>
        )}

        <Input
          id="email"
          name="email"
          type="email"
          label={t("Email address", "نشانی ایمیل")}
          placeholder="you@example.com"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <PasswordField
          id="password"
          name="password"
          label={t("Password", "گذرواژه")}
          placeholder={t("Enter your password", "گذرواژه خود را وارد کنید")}
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          action={<Link href="/forgot-password">{t("Forgot password?", "گذرواژه را فراموش کرده‌اید؟")}</Link>}
          required
        />

        <Button
          type="submit"
          loading={loading}
          className={styles.submit}
        >
          {t("Sign in", "ورود")}
        </Button>
      </form>

      <p className={styles.footer}>
        {t("Don't have an account?", "حساب کاربری ندارید؟")}{" "}
        <Link
          href="/register"
          onClick={(event) => {
            event.preventDefault();
            router.push(getRegisterPath());
          }}
        >
          {t("Create one", "ثبت‌نام")}
        </Link>
      </p>
    </AuthShell>
  );
}
