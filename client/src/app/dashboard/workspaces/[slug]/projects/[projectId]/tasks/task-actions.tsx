"use client";

import { useEffect, useRef, useState } from "react";
import type { Task } from "@/lib/api";
import styles from "./tasks.module.css";

export default function TaskActions({
  task,
  canDelete,
  disabled,
  onOpen,
  onMove,
  onDelete,
}: {
  task: Task;
  canDelete: boolean;
  disabled: boolean;
  onOpen: () => void;
  onMove: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const overflow = document.body.style.overflow;
    if (window.matchMedia("(max-width: 767px)").matches)
      document.body.style.overflow = "hidden";
    function pointer(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        trigger.current?.focus();
        return;
      }
      const items = Array.from(
        ref.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ??
          [],
      ).filter((item) => item.getClientRects().length);
      const index = items.findIndex((item) => item === document.activeElement);
      if (!items.length) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        items[
          (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) %
            items.length
        ]?.focus();
      }
      if (
        event.key === "Tab" &&
        window.matchMedia("(max-width: 767px)").matches &&
        ((event.shiftKey && index === 0) ||
          (!event.shiftKey && index === items.length - 1))
      ) {
        event.preventDefault();
        items[event.shiftKey ? items.length - 1 : 0]?.focus();
      }
    }
    ref.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("pointerdown", pointer);
      document.removeEventListener("keydown", keydown);
    };
  }, [open]);
  return (
    <div className={styles.taskActions} ref={ref} data-task-actions>
      <button
        type="button"
        ref={trigger}
        className={styles.moreButton}
        disabled={disabled}
        aria-label={`Actions for ${task.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        ···
      </button>
      {open && (
        <>
          <div
            className={styles.menuBackdrop}
            onClick={() => {
              setOpen(false);
              trigger.current?.focus();
            }}
          />
          <div
            role="menu"
            aria-label={`Actions for ${task.title}`}
            className={styles.actionMenu}
            onBlur={(event) => {
              if (
                !event.currentTarget.contains(event.relatedTarget as Node) &&
                !trigger.current?.contains(event.relatedTarget as Node)
              )
                setOpen(false);
            }}
          >
            <p>{task.title}</p>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onOpen();
              }}
            >
              Open task
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onMove();
              }}
            >
              Move task
            </button>
            {canDelete && (
              <button
                type="button"
                role="menuitem"
                className={styles.removeAction}
                onClick={() => {
                  setOpen(false);
                  onDelete();
                }}
              >
                Delete task
              </button>
            )}
            <button
              type="button"
              role="menuitem"
              className={styles.menuClose}
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  );
}
