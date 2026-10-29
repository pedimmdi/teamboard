
"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { WorkspaceProvider } from "./workspace-context";

import {
  ApiError,
  getWorkspace,
  type Workspace,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import WorkspaceNav from "./workspace-nav";
import styles from "./workspace-layout.module.css";

type Props = {
  children: ReactNode;
};

export default function WorkspaceLayout({ children }: Props) {
  const { slug } = useParams<{ slug: string }>();
  const { accessToken } = useAuth();

  const [workspace, setWorkspace] =
    useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!accessToken || !slug) return;

    let cancelled = false;

    async function loadWorkspace() {
      setIsLoading(true);
      setError(null);
      setWorkspace(null);

      try {
        const data = await getWorkspace(accessToken!, slug);

        if (!cancelled) {
          setWorkspace(data);
        }
      } catch (err) {
        if (cancelled) return;

        if (err instanceof ApiError && err.status === 404) {
          setError("Workspace not found or access denied.");
        } else if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load workspace.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, [accessToken, slug, reloadKey]);

  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <Link
          href="/dashboard/workspaces"
          className={styles.backLink}
        >
          ← Back to workspaces
        </Link>

        {isLoading ? (
          <div className={styles.statusCard}>
            Loading workspace...
          </div>
        ) : error ? (
          <div className={styles.statusCard} role="alert">
            <p className={styles.error}>{error}</p>
            <button
              type="button"
              className={styles.retryButton}
              onClick={() => setReloadKey((value) => value + 1)}
            >
              Try again
            </button>
          </div>
        ) : workspace ? (
          <>
            <header className={styles.header}>
              <div className={styles.orgIcon}>
                {workspace.name.trim().charAt(0).toUpperCase()}
              </div>

              <div>
                <h1>{workspace.name}</h1>
                <p>Workspace workspace</p>
              </div>
            </header>

            <WorkspaceProvider
              workspace={workspace}
              updateWorkspace={setWorkspace}
            >
              <WorkspaceNav slug={slug} />

              <div className={styles.pageContent}>{children}</div>
            </WorkspaceProvider>
          </>
        ) : (
          <div className={styles.statusCard}>
            Workspace information is unavailable.
          </div>
        )}
      </div>
    </div>
  );
}
