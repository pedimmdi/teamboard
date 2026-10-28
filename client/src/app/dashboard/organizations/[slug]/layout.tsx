
"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { OrganizationProvider } from "./organization-context";

import {
  ApiError,
  getOrganization,
  type Organization,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import OrganizationNav from "./organization-nav";
import styles from "./organization-layout.module.css";

type Props = {
  children: ReactNode;
};

export default function OrganizationLayout({ children }: Props) {
  const { slug } = useParams<{ slug: string }>();
  const { accessToken } = useAuth();

  const [organization, setOrganization] =
    useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!accessToken || !slug) return;

    let cancelled = false;

    async function loadOrganization() {
      setIsLoading(true);
      setError(null);
      setOrganization(null);

      try {
        const data = await getOrganization(accessToken!, slug);

        if (!cancelled) {
          setOrganization(data);
        }
      } catch (err) {
        if (cancelled) return;

        if (err instanceof ApiError && err.status === 404) {
          setError("Organization not found or access denied.");
        } else if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load organization.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadOrganization();

    return () => {
      cancelled = true;
    };
  }, [accessToken, slug, reloadKey]);

  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <Link
          href="/dashboard/organizations"
          className={styles.backLink}
        >
          ← Back to organizations
        </Link>

        {isLoading ? (
          <div className={styles.statusCard}>
            Loading organization...
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
        ) : organization ? (
          <>
            <header className={styles.header}>
              <div className={styles.orgIcon}>
                {organization.name.trim().charAt(0).toUpperCase()}
              </div>

              <div>
                <h1>{organization.name}</h1>
                <p>Organization workspace</p>
              </div>
            </header>

            <OrganizationProvider organization={organization}>
              <OrganizationNav slug={slug} />

              <div className={styles.pageContent}>{children}</div>
            </OrganizationProvider>
          </>
        ) : (
          <div className={styles.statusCard}>
            Organization information is unavailable.
          </div>
        )}
      </div>
    </div>
  );
}
