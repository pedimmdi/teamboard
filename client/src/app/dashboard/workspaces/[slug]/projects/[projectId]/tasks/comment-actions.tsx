import Image from "next/image";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import styles from "./task-comments.module.css";

export default function CommentActions({
  author,
  disabled,
  onEdit,
  onDelete,
}: {
  author: string;
  disabled: boolean;
  onEdit?: () => void;
  onDelete: () => void;
}) {
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const open = position !== null;
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector("button")?.focus();
    function dismiss(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setPosition(null);
    }
    function reposition() {
      if (!window.matchMedia("(max-width: 767px)").matches)
        setPosition(null);
    }
    document.addEventListener("pointerdown", dismiss);
    window.addEventListener("scroll", reposition, true);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open]);

  function close() {
    setPosition(null);
    trigger.current?.focus();
  }

  return (
    <div
      className={styles.actionRoot}
      ref={root}
      onKeyDown={(event) => {
        if (open && event.key === "Escape") {
          event.preventDefault();
          close();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node))
          setPosition(null);
      }}
    >
      <button
        type="button"
        className={styles.more}
        aria-label={`Comment actions for ${author}`}
        aria-expanded={open}
        disabled={disabled}
        ref={trigger}
        onClick={(event) => {
          if (open) {
            close();
            return;
          }
          const rect = event.currentTarget.getBoundingClientRect();
          const menuHeight = onEdit ? 90 : 52;
          setPosition({
            top: rect.bottom + menuHeight <= window.innerHeight
              ? rect.bottom
              : rect.top - menuHeight,
            right: window.innerWidth - rect.right,
          });
        }}
      >
        <Image src="/icons/comments/more.svg" alt="" width={20} height={20} />
      </button>
      {position && (
        <>
          <div className={styles.actionBackdrop} onMouseDown={close} />
          <div
            ref={panel}
            className={styles.actionPanel}
            style={{
              "--comment-menu-top": `${position.top}px`,
              "--comment-menu-right": `${position.right}px`,
            } as CSSProperties}
          >
            <p className={styles.actionHeading}>Comment by {author}</p>
            {onEdit && (
              <button type="button" onClick={() => { close(); onEdit(); }}>
                <Image src="/icons/comments/edit.svg" alt="" width={20} height={20} />
                Edit comment
              </button>
            )}
            <button type="button" className={styles.remove} onClick={() => { close(); onDelete(); }}>
              <Image src="/icons/comments/delete.svg" alt="" width={20} height={20} />
              Delete comment
            </button>
            <button type="button" className={styles.actionCancel} onClick={close}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}
