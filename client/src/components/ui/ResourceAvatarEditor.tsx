"use client";

import { useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import Avatar from "./Avatar";
import styles from "./resource-avatar.module.css";

export default function ResourceAvatarEditor({
  name,
  avatar,
  label,
  onSave,
}: {
  name: string;
  avatar: string | null;
  label: string;
  onSave: (image: File | null) => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  async function save(image: File | null) {
    if (pending) return;
    setPending(true);
    setError("");
    setFeedback("");
    try {
      await onSave(image);
      setFeedback(image ? "Image saved." : "Image removed.");
    } catch (error) {
      const detail = error instanceof ApiError ? error.errors?.avatar : undefined;
      setError(Array.isArray(detail) ? detail.join(" ") : detail || (
        error instanceof Error ? error.message : "Unable to save the image."
      ));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={styles.card}>
      <h2>{label}</h2>
      <div className={styles.controls}>
        <Avatar className={styles.avatar} src={avatar} fallback={name.charAt(0).toUpperCase()} size={48} />
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void save(file);
          }}
        />
        <button type="button" disabled={pending} onClick={() => input.current?.click()}>
          {pending ? "Saving…" : "Upload image"}
        </button>
        {avatar && <button type="button" disabled={pending} onClick={() => void save(null)}>Remove image</button>}
      </div>
      <p>JPEG, PNG or WebP up to 5 MB.</p>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {feedback && <p role="status">{feedback}</p>}
    </section>
  );
}
