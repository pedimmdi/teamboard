"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import styles from "./tasks.module.css";

export default function TaskDialog({
  title,
  description,
  children,
  onClose,
  busy = false,
  drawer = false,
  headerAction,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
  drawer?: boolean;
  headerAction?: ReactNode;
}) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  const pending = useRef(busy);
  useEffect(() => {
    close.current = onClose;
    pending.current = busy;
  }, [onClose, busy]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      if (event.key === "Escape" && !pending.current) {
        event.preventDefault();
        close.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)",
        ) ?? [],
      ).filter((item) => item.getClientRects().length);
      if (!items.length) {
        event.preventDefault();
        return;
      }
      const first = items[0],
        last = items[items.length - 1];
      if (!ref.current?.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === ref.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === ref.current)
      ) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className={`${styles.overlay} ${drawer ? styles.drawerOverlay : ""}`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending.current) onClose();
      }}
    >
      <div
        className={drawer ? styles.drawer : styles.dialog}
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={description ? `${id}-description` : undefined}
        tabIndex={-1}
      >
        <header className={styles.dialogHeader}>
          <h2 id={`${id}-title`}>{title}</h2>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.iconButton}
              onClick={onClose}
              disabled={busy}
              aria-label={drawer ? "Back to tasks" : "Close dialog"}
            >
              {drawer ? (
                <>
                  <span className={styles.desktopClose}>×</span>
                  <span className={styles.mobileBack}>←</span>
                </>
              ) : (
                "×"
              )}
            </button>
            {headerAction}
          </div>
        </header>
        {description && (
          <p id={`${id}-description`} className={styles.muted}>
            {description}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}
