"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { useAuth } from "@/lib/auth";

import styles from "./dashboard.module.css";

type DashboardLayoutProps = {
  children: ReactNode;
};

function BrandMark() {
  return (
    <span className={styles.brandMark} aria-hidden="true">
      <svg viewBox="0 0 18 18" fill="none">
        <rect x="3" y="4" width="3" height="10" rx="1" fill="currentColor" />
        <rect x="7.5" y="6" width="3" height="8" rx="1" fill="currentColor" />
        <rect x="12" y="3" width="3" height="11" rx="1" fill="currentColor" />
      </svg>
    </span>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="6.5" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M4.5 16.5C4.5 13.6 6.75 11.5 10 11.5C13.25 11.5 15.5 13.6 15.5 16.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect
        x="4"
        y="8"
        width="12"
        height="9"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M6.5 8V6C6.5 4.07 8.07 2.5 10 2.5C11.93 2.5 13.5 4.07 13.5 6V8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MonitorIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect
        x="2.5"
        y="3"
        width="15"
        height="10"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M7 17H13M10 13V17"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function OrganizationIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="3"
        y="3"
        width="14"
        height="14"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M7 17V8H13V17"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M5.5 6H5.51M9.5 6H9.51M13.5 6H13.51"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M8 3H4.5C3.67 3 3 3.67 3 4.5V15.5C3 16.33 3.67 17 4.5 17H8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M11 6L15 10L11 14M7.5 10H15"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function NavItem({
  href,
  label,
  active,
  icon,
}: {
  href: string;
  label: string;
  active: boolean;
  icon: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`${styles.navItem} ${active ? styles.navItemActive : ""}`}
    >
      <span className={styles.navIcon}>{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

function getInitials(firstName: string, lastName: string) {
  const first = firstName.trim().charAt(0);
  const last = lastName.trim().charAt(0);

  return `${first}${last}`.toUpperCase() || "U";
}

export default function DashboardLayout({
  children,
}: DashboardLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated || !user) {
    return null;
  }

  const initials = getInitials(user.first_name, user.last_name);

  const isOrganizations =
    pathname === "/dashboard/organizations" ||
    pathname.startsWith("/dashboard/organizations/");

  const isProfile = pathname === "/dashboard";
  const isSecurity = pathname === "/dashboard/security";
  const isSessions = pathname === "/dashboard/sessions";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <div className={styles.dashboard}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <div className={styles.brand}>
            <BrandMark />
            <span>TeamBoard</span>
          </div>

          <nav className={styles.navigation} aria-label="Workspace">
            <div className={styles.sectionLabel}>
              WORKSPACE
            </div>

            <NavItem
              href="/dashboard/organizations"
              label="Organizations"
              active={isOrganizations}
              icon={<OrganizationIcon />}
            />

            <div className={styles.sectionLabel}>
              ACCOUNT
            </div>

            <NavItem
              href="/dashboard"
              label="Profile"
              active={isProfile}
              icon={<UserIcon />}
            />

            <NavItem
              href="/dashboard/security"
              label="Security"
              active={isSecurity}
              icon={<LockIcon />}
            />

            <NavItem
              href="/dashboard/sessions"
              label="Sessions"
              active={isSessions}
              icon={<MonitorIcon />}
            />
          </nav>
        </div>

        <div className={styles.sidebarBottom}>
          <button
            type="button"
            className={styles.signOutButton}
            onClick={handleLogout}
          >
            <span className={styles.navIcon}>
              <LogoutIcon />
            </span>
            <span>Sign out</span>
          </button>

          <div className={styles.userSummary}>
            <div className={styles.smallAvatar}>{initials}</div>

            <div className={styles.userSummaryText}>
              <div className={styles.userName}>
                {user.first_name} {user.last_name}
              </div>
              <div className={styles.userEmail}>{user.email}</div>
            </div>
          </div>
        </div>
      </aside>

      <header className={styles.mobileHeader}>
        <div className={styles.brand}>
          <BrandMark />
          <span>TeamBoard</span>
        </div>

        <button
          type="button"
          className={styles.mobileLogoutButton}
          onClick={handleLogout}
          aria-label="Sign out"
        >
          <LogoutIcon />
        </button>
      </header>

      <main className={styles.main}>{children}</main>

      <nav
        className={styles.mobileTabBar}
        aria-label="Dashboard"
      >
        <NavItem
          href="/dashboard/organizations"
          label="Organizations"
          active={isOrganizations}
          icon={<OrganizationIcon />}
        />

        <NavItem
          href="/dashboard"
          label="Profile"
          active={isProfile}
          icon={<UserIcon />}
        />

        <NavItem
          href="/dashboard/security"
          label="Security"
          active={isSecurity}
          icon={<LockIcon />}
        />

        <NavItem
          href="/dashboard/sessions"
          label="Sessions"
          active={isSessions}
          icon={<MonitorIcon />}
        />
      </nav>
    </div>
  );
}