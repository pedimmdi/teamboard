"use client";
import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import styles from "@/app/(public)/website.module.css";
export default function ContactForm() {
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    busy.current = true;
    setPending(true);
    setError("");
    setFields({});
    setSuccess(false);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/website/contact/`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
          credentials: "omit",
        },
      );
      if (response.status === 413)
        throw new Error(
          "Your message is too large. Please shorten it and try again.",
        );
      if (response.status === 429) {
        const delay = response.headers.get("Retry-After");
        throw new Error(
          `Too many messages. Please ${delay ? `wait ${delay} seconds` : `wait a little`} before trying again.`,
        );
      }
      if (response.status === 400) {
        const body = await response.json();
        setFields(
          Object.fromEntries(
            Object.entries(body.errors ?? body)
              .filter(([key]) =>
                ["name", "email", "subject", "message"].includes(key),
              )
              .map(([key, value]) => [
                key,
                Array.isArray(value) ? value.join(" ") : String(value),
              ]),
          ),
        );
        throw new Error("Please check the highlighted fields and try again.");
      }
      if (!response.ok)
        throw new Error("Unable to send your message. Please try again later.");
      setSuccess(true);
      form.reset();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to connect. Please try again.",
      );
    } finally {
      busy.current = false;
      setPending(false);
    }
  }
  return (
    <form className={styles.form} onSubmit={submit}>
      {success && (
        <p role="status">
          Your message has been received. Thank you for getting in touch.
        </p>
      )}
      {error && (
        <p role="alert" id="contact-error">
          {error}
        </p>
      )}
      {[
        ["name", "Your name", 120],
        ["email", "Email address", 254],
        ["subject", "Subject", 180],
        ["message", "Message", 5000],
      ].map(([name, label, max]) => (
        <div key={name}>
          <label htmlFor={`contact-${name}`}>{label}</label>
          {name === "message" ? (
            <textarea
              id={`contact-${name}`}
              name={String(name)}
              required
              maxLength={Number(max)}
              rows={7}
              disabled={pending}
              aria-invalid={Boolean(fields[name])}
              aria-describedby={fields[name] ? `${name}-error` : undefined}
            />
          ) : (
            <input
              id={`contact-${name}`}
              name={String(name)}
              type={name === "email" ? "email" : "text"}
              autoComplete={
                name === "name" ? "name" : name === "email" ? "email" : "off"
              }
              required
              maxLength={Number(max)}
              disabled={pending}
              aria-invalid={Boolean(fields[name])}
              aria-describedby={fields[name] ? `${name}-error` : undefined}
            />
          )}{" "}
          {fields[name] && <small id={`${name}-error`}>{fields[name]}</small>}
        </div>
      ))}
      <div className={styles.honeypot} aria-hidden="true">
        <label htmlFor="website-url">Website URL</label>
        <input
          id="website-url"
          name="website_url"
          tabIndex={-1}
          autoComplete="off"
        />
      </div>
      <p>
        Contact messages are kept for up to 180 days. Read our{" "}
        <Link href="/privacy">Privacy policy</Link>.
      </p>
      <button className={styles.primary} disabled={pending}>
        {pending ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
