"use client";

import { useEffect, useState } from "react";
import CreateWorkspaceModal from "./create-workspace-modal";
import Link from "next/link";

import {
  ApiError,
  getWorkspaces,
  type Workspace,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import styles from "./workspaces.module.css";

function formatCreatedDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function getWorkspaceInitial(name: string) {
  return name.trim().charAt(0).toUpperCase() || "O";
}

function getRoleLabel(role: Workspace["role"]) {
  switch (role?.toUpperCase()) {
    case "OWNER":
      return "Owner";

    case "ADMIN":
      return "Admin";

    case "MEMBER":
      return "Member";

    default:
      return "Unknown";
  }
}

function getRoleClassName(
  role: Workspace["role"],
) {
  switch (role?.toUpperCase()) {
    case "OWNER":
      return styles.roleOwner;

    case "ADMIN":
      return styles.roleAdmin;

    default:
      return styles.roleMember;
  }
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

function WorkspaceIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="4"
        y="4"
        width="16"
        height="16"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M8 20V9H16V20"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M7 7H7.01M11 7H11.01M15 7H15.01"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function WorkspacesPage() {
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
            "Unable to load workspaces. Please try again.",
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
  }, [accessToken, page, reloadKey]);

  const startItem =
    count === 0 ? 0 : (page - 1) * workspaces.length + 1;

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
            <h1>Workspaces</h1>

            <p>
              Workspaces you belong to.
            </p>
          </div>

          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => setIsCreateOpen(true)}
            disabled={!accessToken}
          >
            Create workspace
          </button>
        </header>

        {isLoading ? (
          <div className={styles.loadingState}>
            <div className={styles.loadingRow} />
            <div className={styles.loadingRow} />
            <div className={styles.loadingRow} />
          </div>
        ) : error ? (
          <div className={styles.errorState}>
            <p>{error}</p>

            <button
              type="button"
              className={styles.secondaryButton}
              onClick={() => setPage(1)}
            >
              Try again
            </button>
          </div>
        ) : workspaces.length === 0 ? (
          <section className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <WorkspaceIcon />
            </div>

            <h2>No workspaces yet</h2>

            <p>
              Create your first workspace, or accept an
              invitation sent to your email address.
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
                  )}`}
                  className={styles.workspaceCard}
                >
                  <div className={styles.workspaceIcon}>
                    {getWorkspaceInitial(
                      workspace.name,
                    )}
                  </div>

                  <div className={styles.workspaceInfo}>
                    <div className={styles.workspaceName}>
                      {workspace.name}
                    </div>

                    <div className={styles.workspaceDate}>
                      Created{" "}
                      {formatCreatedDate(
                        workspace.created_at,
                      )}
                    </div>
                  </div>

                  <span
                    className={`${styles.roleBadge} ${getRoleClassName(
                      workspace.role,
                    )}`}
                  >
                    {getRoleLabel(workspace.role)}
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
                Showing {startItem}–{endItem} of {count}
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
                  Previous
                </button>

                <button
                  type="button"
                  className={styles.paginationButton}
                  disabled={!hasNext}
                  onClick={() =>
                    setPage((current) => current + 1)
                  }
                >
                  Next
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