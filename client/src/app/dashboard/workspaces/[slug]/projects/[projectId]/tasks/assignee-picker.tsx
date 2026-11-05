"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ProjectMember } from "@/lib/api";
import Avatar from "@/components/ui/Avatar";
import styles from "./tasks.module.css";

export default function AssigneePicker({
  members,
  value,
  onChange,
  filter = false,
  disabled = false,
  loading = false,
  error,
  onRetry,
}: {
  members: ProjectMember[];
  value: string;
  onChange: (value: string) => void;
  filter?: boolean;
  disabled?: boolean;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();
  const me = members.find((member) => member.is_current_user);
  const options = [
    ...(filter
      ? [
          { value: "", label: "Anyone", avatar: null },
          { value: "me", label: "Me", avatar: me?.avatar },
        ]
      : []),
    { value: filter ? "unassigned" : "", label: "Unassigned", avatar: null },
    ...(!filter && me
      ? [
          {
            value: String(me.user_id),
            label: "Assign to me",
            avatar: me.avatar,
          },
        ]
      : []),
    ...members
      .filter((member) => filter || !member.is_current_user)
      .map((member) => ({
        value: String(member.user_id),
        label: member.user_email,
        avatar: member.avatar,
      })),
  ];
  const selected = options.find((option) => option.value === value);
  const label =
    selected?.label ??
    (value ? "Current assignee" : filter ? "Anyone" : "Unassigned");
  useEffect(() => {
    if (!open) return;
    const button = trigger.current;
    const previousOverflow = document.body.style.overflow;
    if (window.matchMedia("(max-width: 767px)").matches)
      document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLInputElement>("input")?.focus();
    function pointer(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        setOpen(false);
        button?.focus();
        return;
      }
      const items = Array.from(
        panel.current?.querySelectorAll<HTMLElement>(
          "input, button:not(:disabled)",
        ) ?? [],
      ).filter((item) => item.getClientRects().length);
      if (!items.length) return;
      const index = items.findIndex((item) => item === document.activeElement);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        items[
          (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) %
            items.length
        ]?.focus();
      }
      if (
        event.key === "Tab" &&
        ((event.shiftKey && index === 0) ||
          (!event.shiftKey && index === items.length - 1))
      ) {
        event.preventDefault();
        items[event.shiftKey ? items.length - 1 : 0]?.focus();
      }
    }
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keydown, true);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("pointerdown", pointer);
      document.removeEventListener("keydown", keydown, true);
    };
  }, [open]);
  return (
    <div className={styles.picker} ref={ref}>
      <button
        className={`${styles.selectButton} ${filter && value ? styles.activeFilter : ""}`}
        type="button"
        ref={trigger}
        disabled={disabled}
        aria-label={
          filter ? `Filter by assignee: ${label}` : `Assignee: ${label}`
        }
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => {
          setSearch("");
          setOpen((current) => !current);
        }}
      >
        <span>
          {filter ? (value ? `Assignee · ${label}` : "Assignee") : label}
        </span>
        <span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <>
          <div
            className={styles.pickerBackdrop}
            onClick={() => {
              setOpen(false);
              trigger.current?.focus();
            }}
          />
          <div
            className={styles.pickerPanel}
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label="Assignee"
            id={id}
          >
            <h3>Assignee</h3>
            <p className={styles.hint}>
              {filter
                ? "Filter by who is assigned."
                : "Only project members can be assigned."}
            </p>
            <input
              aria-label="Search members"
              placeholder="Search members…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {loading && (
              <p className={styles.hint} role="status">
                Loading project members…
              </p>
            )}
            {error && (
              <>
                <p className={styles.error} role="alert">
                  {error}
                </p>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={onRetry}
                >
                  Retry members
                </button>
              </>
            )}
            <div className={styles.pickerOptions}>
              {options
                .filter((option) =>
                  option.label.toLowerCase().includes(search.toLowerCase()),
                )
                .map((option) => (
                  <button
                    key={option.value || "any"}
                    type="button"
                    aria-pressed={value === option.value}
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                      trigger.current?.focus();
                    }}
                  >
                    <Avatar
                      src={option.avatar}
                      fallback={option.label.charAt(0).toUpperCase()}
                      className={styles.avatar}
                      size={24}
                    />
                    <span>{option.label}</span>
                    {value === option.value && (
                      <span aria-hidden="true">✓</span>
                    )}
                  </button>
                ))}
            </div>
            {!options.some((option) =>
              option.label.toLowerCase().includes(search.toLowerCase()),
            ) && <p className={styles.hint}>No members match your search.</p>}
            <button
              className={`${styles.secondaryButton} ${styles.pickerClose}`}
              type="button"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              Close
            </button>
          </div>
        </>
      )}
    </div>
  );
}
