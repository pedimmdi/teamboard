"use client";

import { useLocale } from "@/lib/preferences";
import { localizeAccountMessage } from "@/lib/account-message";
import { useEffect, useState } from "react";
import CreateWorkspaceModal from "./create-workspace-modal";
import Avatar from "@/components/ui/Avatar";
import Link from "next/link";
import WorkspaceIcon from "@/components/ui/WorkspaceIcon";

import {
  ApiError,
  getWorkspaces,
  type Workspace,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import styles from "./workspaces.module.css";

import { workspaceRoleLabel } from "../workspace-role";

const WORKSPACE_PAGE_SIZE = 20;

function getWorkspaceInitial(name: string) {
  return name.trim().charAt(0).toUpperCase() || "O";
}

function ChevronRightIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M7.5 4.5L13 10L7.5 15.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function WorkspacesPage() {
  const { locale, t, formatDate, formatNumber } = useLocale();
  const { accessToken } = useAuth();

  const [workspaces, setWorkspaces] = useState<
    Workspace[]
  >([]);

  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);

  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] =
    useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(
    null,
  );

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const token = accessToken;
    let cancelled = false;

    async function loadWorkspaces() {
      setIsLoading(true);
      setError(null);

      try {
        const data = await getWorkspaces(
          token,
          page,
        );

        if (cancelled) {
          return;
        }

        setWorkspaces(data.results);
        setCount(data.count);
        setHasNext(Boolean(data.next));
        setHasPrevious(Boolean(data.previous));
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (error instanceof ApiError) {
          setError(error.message);
        } else {
          setError(
            t("Unable to load workspaces. Please try again.", "فضاهای کاری بارگیری نشدند. دوباره تلاش کنید."),
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, [accessToken, page, reloadKey, t]);

  const startItem =
    count === 0 ? 0 : (page - 1) * WORKSPACE_PAGE_SIZE + 1;

  const endItem =
    count === 0
      ? 0
      : Math.min(
          startItem + workspaces.length - 1,
          count,
        );

  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <header className={styles.header}>
          <div>
            <h1>{t("Workspaces", "فضاهای کاری")}</h1>

            <p>
              {t("Workspaces you belong to.", "فضاهای کاری که در آن‌ها عضویت دارید.")}
            </p>
          </div>

          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => setIsCreateOpen(true)}
            disabled={!accessToken}
          >
            {t("Create workspace", "ایجاد فضای کاری")}
          </button>
        </header>

        {isLoading ? (
          <div className={styles.loadingState} role="status">
            {t("Loading workspaces…", "در حال بارگیری فضاهای کاری…")}
          </div>
        ) : error ? (
          <div className={styles.errorState} role="alert">
            <p>{localizeAccountMessage(locale, error, "فضاهای کاری بارگیری نشدند. دوباره تلاش کنید.")}</p>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => setReloadKey((key) => key + 1)}
            >
              {t("Try again", "تلاش دوباره")}
            </button>
          </div>
        ) : workspaces.length === 0 ? (
          <section className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <WorkspaceIcon />
            </div>

            <h2>{t("No workspaces yet", "هنوز فضای کاری ندارید")}</h2>

            <p>
              {t("Create your first workspace, or accept an invitation sent to your email address.", "اولین فضای کاری خود را بسازید یا دعوتی را که به ایمیل‌تان رسیده بپذیرید.")}
            </p>
          </section>
        ) : (
          <>
            <div className={styles.workspaceList}>
              {workspaces.map((workspace) => (
                <Link
                  key={workspace.id}
                  href={`/dashboard/workspaces/${encodeURIComponent(
                    workspace.slug,
                  )}/dashboard`}
                  className={styles.workspaceCard}
                >
                  <Avatar className={styles.workspaceIcon} src={workspace.avatar} fallback={getWorkspaceInitial(workspace.name)} />

                  <div className={styles.workspaceInfo}>
                    <div className={styles.workspaceName} dir="auto">
                      {workspace.name}
                    </div>

                    <div className={styles.workspaceDate}>
                      {t("Created", "تاریخ ایجاد")}{" "}
                      <time dateTime={workspace.created_at}>
                        {formatDate(workspace.created_at, { month: "short", day: "2-digit", year: "numeric" })}
                      </time>
                    </div>
                  </div>

                  <span
                    className={styles.roleBadge} data-role-tone={workspace.role ?? "member"}
                  >
                    {workspaceRoleLabel(workspace.role, locale)}
                  </span>

                  <span
                    className={styles.chevron}
                    aria-hidden="true"
                  >
                    <ChevronRightIcon />
                  </span>
                </Link>
              ))}
            </div>

            <div className={styles.pagination}>
              <span className={styles.paginationInfo}>
                {t("Showing", "نمایش")} <bdi>{formatNumber(startItem)}–{formatNumber(endItem)}</bdi> {t("of", "از")} {formatNumber(count)}
              </span>

              <div className={styles.paginationActions}>
                <button
                  type="button"
                  className={styles.paginationButton}
                  disabled={!hasPrevious}
                  onClick={() =>
                    setPage((current) =>
                      Math.max(1, current - 1),
                    )
                  }
                >
                  {t("Previous", "قبلی")}
                </button>

                <button
                  type="button"
                  className={styles.paginationButton}
                  disabled={!hasNext}
                  onClick={() =>
                    setPage((current) => current + 1)
                  }
                >
                  {t("Next", "بعدی")}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {isCreateOpen && accessToken && (
        <CreateWorkspaceModal
          accessToken={accessToken}
          onClose={() => setIsCreateOpen(false)}
          onCreated={() => {
            setIsCreateOpen(false);
            setPage(1);
            setReloadKey((current) => current + 1);
          }}
        />
      )}
    </div>
  );
}
