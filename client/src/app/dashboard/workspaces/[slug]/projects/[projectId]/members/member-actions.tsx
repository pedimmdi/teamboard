"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ProjectMember } from "@/lib/api";
import styles from "../../projects.module.css";

export default function MemberActions({
  member,
  canAssignManagers,
  canManage,
  onRole,
  onRemove,
}: {
  member: ProjectMember;
  canAssignManagers: boolean;
  canManage: boolean;
  onRole: () => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();
  const canRemove =
    canManage &&
    !member.is_current_user &&
    (canAssignManagers || member.role !== "manager");
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    if (window.matchMedia("(max-width: 767px)").matches)
      document.body.style.overflow = "hidden";
    function pointer(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
      const items = Array.from(
        ref.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ??
          [],
      ).filter((item) => item.getClientRects().length > 0);
      if (!items.length) return;
      if (
        event.key === "Tab" &&
        window.matchMedia("(max-width: 767px)").matches
      ) {
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const index = items.findIndex((item) => item === document.activeElement);
      items[
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? items.length - 1
            : (index + (event.key === "ArrowUp" ? -1 : 1) + items.length) %
              items.length
      ]?.focus();
    }
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keydown);
    ref.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("pointerdown", pointer);
      document.removeEventListener("keydown", keydown);
    };
  }, [open]);
  if (!canAssignManagers && !canRemove) return null;
  return (
    <div className={styles.memberActions} ref={ref}>
      <button
        className={styles.iconButton}
        ref={button}
        aria-label={`Actions for ${member.user_email}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((value) => !value)}
      >
        ···
      </button>
      {open && (
        <>
          <div className={styles.menuBackdrop} onClick={() => setOpen(false)} />
          <div
            className={styles.actionMenu}
            role="menu"
            id={id}
            aria-label={`Actions for ${member.user_email}`}
            onBlur={(event) => {
              if (
                !event.currentTarget.contains(event.relatedTarget as Node) &&
                !button.current?.contains(event.relatedTarget as Node)
              )
                setOpen(false);
            }}
          >
            <p className={styles.mobileMenuTitle}>{member.user_email}</p>
            {canAssignManagers && (
              <button
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onRole();
                }}
              >
                {member.role === "manager" ? "Make member" : "Make manager"}
              </button>
            )}
            {canRemove && (
              <button
                role="menuitem"
                className={styles.removeAction}
                onClick={() => {
                  setOpen(false);
                  onRemove();
                }}
              >
                Remove from project
              </button>
            )}
            <button
              className={styles.mobileMenuClose}
              role="menuitem"
              onClick={() => {
                setOpen(false);
                button.current?.focus();
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
