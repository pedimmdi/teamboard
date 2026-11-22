"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getWorkspace, getWorkspaces, type Workspace } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/ui/Avatar";
import DesignIcon from "@/components/ui/DesignIcon";
import CreateWorkspaceModal from "./workspaces/create-workspace-modal";
import { workspaceRoleLabel } from "./workspace-role";
import styles from "./workspace-switcher.module.css";

export default function WorkspaceSwitcher({
  slug,
  mobile = false,
}: {
  slug?: string;
  mobile?: boolean;
}) {
  const { locale, t } = useLocale();
  const { accessToken } = useAuth();
  const router = useRouter();
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [items, setItems] = useState<Workspace[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!accessToken || !slug) return;
    let cancelled = false;
    getWorkspace(accessToken, slug)
      .then((workspace) => {
        if (!cancelled) setSelected(workspace);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [accessToken, slug]);
  useEffect(() => {
    if (!open || !accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const workspaces: Workspace[] = [];
        let page = 1;
        while (true) {
          const data = await getWorkspaces(accessToken!, page);
          if (cancelled) return;
          workspaces.push(...data.results);
          if (!data.next) break;
          page++;
        }
        setItems(workspaces);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : t("Unable to load workspaces.", "فضاهای کاری بارگیری نشدند."),
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, accessToken, reload, t]);
  useEffect(() => {
    if (!open) return;
    const triggerButton = trigger.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = ref.current?.querySelectorAll<HTMLElement>(
        "a[href], button:not(:disabled)",
      );
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
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
      triggerButton?.focus();
    };
  }, [open]);
  useEffect(() => {
    function update(event: Event) {
      const workspace = (event as CustomEvent<Workspace>).detail;
      if (workspace.slug === slug) setSelected(workspace);
      setItems((current) => current.map((item) => item.id === workspace.id ? workspace : item));
    }
    window.addEventListener("teamboard:workspace-updated", update);
    return () => window.removeEventListener("teamboard:workspace-updated", update);
  }, [slug]);

  const active = selected?.slug === slug ? selected : null;
  return (
    <div className={`${styles.switcher} ${mobile ? styles.mobile : ""}`}>
      <button
        ref={trigger}
        className={styles.trigger}
        aria-label={t("Switch workspace", "تغییر فضای کاری")}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar className={styles.tile} src={active?.avatar} fallback={active?.name.charAt(0).toUpperCase() || "W"} />
        <span className={styles.identity}>
          <span dir="auto">
            {active?.name ?? (slug ? t("Loading workspace…", "در حال بارگیری فضای کاری…") : t("All workspaces", "همه فضاهای کاری"))}
          </span>
          {!mobile && active && (
            <small><span data-role-tone={active.role ?? "member"}>
              {workspaceRoleLabel(active.role ?? "member", locale)}
            </span></small>
          )}
        </span>
        <DesignIcon name="chevrons-up-down" />
      </button>
      {open && (
        <>
          <div className={styles.backdrop} onClick={() => setOpen(false)} />
          <div
            ref={ref}
            className={styles.panel}
            role="dialog"
            aria-modal="true"
            aria-label={t("Switch workspace", "تغییر فضای کاری")}
            tabIndex={-1}
          >
            <header>
              <strong>{t("Switch workspace", "تغییر فضای کاری")}</strong>
              <button
                onClick={() => setOpen(false)}
                aria-label={t("Close workspace switcher", "بستن انتخاب‌گر فضای کاری")}
              >
                ×
              </button>
            </header>
            <p className={styles.heading}>{t("YOUR WORKSPACES", "فضاهای کاری شما")}</p>
            {loading ? (
              <p className={styles.feedback} role="status">
                {t("Loading workspaces…", "در حال بارگیری فضاهای کاری…")}
              </p>
            ) : error ? (
              <div className={styles.feedback}>
                <p role="alert">{localizeAccountMessage(locale, error, "فضاهای کاری بارگیری نشدند.")}</p>
                <button onClick={() => setReload((value) => value + 1)}>
                  {t("Try again", "تلاش دوباره")}
                </button>
              </div>
            ) : (
              <div className={styles.list}>
                {items.map((workspace) => (
                  <Link
                    key={workspace.id}
                    className={`${styles.item} ${workspace.slug === slug ? styles.selected : ""}`}
                    href={`/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/dashboard`}
                    aria-current={workspace.slug === slug ? "true" : undefined}
                    onClick={() => setOpen(false)}
                  >
                    <Avatar className={styles.tile} src={workspace.avatar} fallback={workspace.name.charAt(0).toUpperCase()} />
                    <span className={styles.identity}>
                      <span dir="auto">{workspace.name}</span>
                      <small><span data-role-tone={workspace.role ?? "member"}>
                        {workspaceRoleLabel(workspace.role ?? "member", locale)}
                      </span></small>
                    </span>
                    {workspace.slug === slug && (
                      <span aria-hidden="true">✓</span>
                    )}
                  </Link>
                ))}
              </div>
            )}
            <footer>
              <Link href="/dashboard/workspaces" onClick={() => setOpen(false)}>
                {t("All workspaces", "همه فضاهای کاری")}
              </Link>
              <button
                onClick={() => {
                  setOpen(false);
                  setCreating(true);
                }}
              >
                {t("＋ Create workspace", "＋ ایجاد فضای کاری")}
              </button>
            </footer>
          </div>
        </>
      )}
      {creating && accessToken && (
        <CreateWorkspaceModal
          accessToken={accessToken}
          onClose={() => setCreating(false)}
          onCreated={(workspace) => {
            setCreating(false);
            router.push(
              `/dashboard/workspaces/${encodeURIComponent(workspace.slug)}/dashboard`,
            );
          }}
        />
      )}
    </div>
  );
}
