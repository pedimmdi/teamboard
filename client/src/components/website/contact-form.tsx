"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import styles from "@/app/(public)/website.module.css";
import { websitePath, type WebsiteLocale } from "@/lib/website";
import { retentionSchedule, websiteCopy } from "@/lib/website-copy";

const fields = [
  { name: "name", maxLength: 120, autoComplete: "name" },
  { name: "email", maxLength: 254, autoComplete: "email" },
  { name: "subject", maxLength: 180, autoComplete: "off" },
  { name: "message", maxLength: 5000 },
] as const;

export default function ContactForm({ locale, retentionDays }: { locale: WebsiteLocale; retentionDays: number | null }) {
  const copy = websiteCopy[locale];
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    busy.current = true;
    setPending(true);
    setError("");
    setFieldErrors({});
    setSuccess(false);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/website/contact/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
          credentials: "omit",
          signal: AbortSignal.timeout(15_000),
        },
      );
      if (response.status === 413) {
        setError(copy.form.large);
      } else if (response.status === 429) {
        const delay = Number(response.headers.get("Retry-After"));
        const seconds = new Intl.NumberFormat(locale).format(delay);
        setError(delay > 0 && Number.isFinite(delay)
          ? locale === "fa"
            ? `تعداد پیام‌ها زیاد است. لطفاً ${seconds} ثانیه صبر کنید و دوباره تلاش کنید.`
            : `Too many messages. Please wait ${seconds} seconds before trying again.`
          : copy.form.rate);
      } else if (response.status === 400) {
        const body = await response.json().catch(() => ({}));
        const errors = body?.errors ?? body ?? {};
        const matchingErrors = fields.flatMap(({ name }) => {
          const value = errors[name];
          return value
            ? [[name, locale === "fa" ? copy.form.field : Array.isArray(value) ? value.join(" ") : String(value)]]
            : [];
        });
        setFieldErrors(Object.fromEntries(matchingErrors));
        setError(matchingErrors.length ? copy.form.check : copy.form.failed);
      } else if (!response.ok) {
        setError(copy.form.failed);
      } else {
        setSuccess(true);
        form.reset();
      }
    } catch {
      setError(copy.form.network);
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  function localizeValidation(event: FormEvent<HTMLFormElement>) {
    if (locale !== "fa") return;
    const field = event.target;
    if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) return;
    const message = field.validity.valueMissing ? "لطفاً این فیلد را پر کنید."
      : field.validity.typeMismatch ? "لطفاً یک نشانی ایمیل معتبر وارد کنید."
      : copy.form.field;
    field.setCustomValidity(message);
  }

  return (
    <form className={styles.form} onSubmit={submit} onInvalid={localizeValidation} onInput={(event) => {
      const field = event.target;
      if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) field.setCustomValidity("");
    }}>
      {success && <p role="status">{copy.form.success}</p>}
      {error && <p role="alert">{error}</p>}
      {fields.map(({ name, ...options }) => {
        const field = {
          id: `contact-${name}`, name, required: true, maxLength: options.maxLength, disabled: pending,
          "aria-invalid": Boolean(fieldErrors[name]),
          "aria-describedby": fieldErrors[name] ? `${name}-error` : undefined,
        };
        return (
          <div className={name === "name" || name === "email" ? styles.formSplit : undefined} key={name}>
            <label htmlFor={field.id}>{copy.form[name]}</label>
            {name === "message" ? <textarea {...field} dir="auto" rows={6} /> : (
              <input {...field} dir={name === "email" ? "ltr" : "auto"} type={name === "email" ? "email" : "text"}
                autoComplete={"autoComplete" in options ? options.autoComplete : undefined} />
            )}
            {fieldErrors[name] && <small id={`${name}-error`}>{fieldErrors[name]}</small>}
          </div>
        );
      })}
      <div className={styles.honeypot} aria-hidden="true">
        <label htmlFor="website-url">{copy.form.trap}</label>
        <input id="website-url" name="website_url" tabIndex={-1} autoComplete="off" />
      </div>
      <p>{retentionSchedule(locale, retentionDays)} <Link href={websitePath("/privacy", locale)}>{copy.privacyTitle}</Link></p>
      <button type="submit" className={styles.primary} disabled={pending}>
        {pending ? copy.form.pending : copy.form.submit}
      </button>
    </form>
  );
}
