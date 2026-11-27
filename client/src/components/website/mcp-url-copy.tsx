"use client";

import { useState } from "react";
import styles from "@/app/(public)/website.module.css";

export default function McpUrlCopy({ url, labels }: {
  url: string;
  labels: { action: string; success: string; failure: string };
}) {
  const [message, setMessage] = useState("");

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setMessage(labels.success);
    } catch {
      setMessage(labels.failure);
    }
  }

  return (
    <div className={styles.mcpUrl}>
      <code dir="ltr">{url}</code>
      <button className={styles.secondary} type="button" onClick={() => void copy()}>{labels.action}</button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
