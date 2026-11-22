"use client";

import { useLocale } from "@/lib/preferences";
import Link from "next/link";
import { ChatUnreadProvider, ChatUnreadBadge, useChatUnread } from "@/components/chats/chat-unread";
import ChatIcon from "@/components/chats/chat-icon";
import ReportIcon from "@/components/reports/report-icon";
import CalendarIcon from "@/components/calendar/calendar-icon";
import Avatar from "@/components/ui/Avatar";
import BrandMark from "@/components/ui/BrandMark";
import DesignIcon from "@/components/ui/DesignIcon";
import { PreferencesControls } from "@/components/preferences-controls";
import { BellIcon, NotificationCountProvider, useNotificationCount } from "./notifications/notification-count";
import WorkspaceSwitcher from "./workspace-switcher";
import { useParams, usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";
import {
  dashboardWorkspaceKey,
  loadDashboardWorkspace,
} from "./dashboard-workspace";

import { useAuth } from "@/lib/auth";

import styles from "./dashboard.module.css";

type DashboardLayoutProps = {
  children: ReactNode;
};

function DashboardBrand() {
  const { t } = useLocale();
  return (
    <div className={styles.brand}>
      <span className={styles.brandMark}><BrandMark /></span>
      <span>{t("TeamBoard", "تیم‌برد")}</span>
    </div>
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
  trailing,
  accessibleLabel,
}: {
  href: string | null;
  label: string;
  active: boolean;
  icon: ReactNode;
  trailing?: ReactNode;
  accessibleLabel?: string;
}) {
  if (!href) {
    return (
      <span
        className={styles.navItem + " " + styles.navItemDisabled}
        aria-disabled="true"
      >
        <span className={styles.navIcon}>{icon}</span>
        <span>{label}</span>
      </span>
    );
  }
  return (
    <Link
      aria-current={active ? "page" : undefined}
      aria-label={accessibleLabel}
      href={href}
      className={`${styles.navItem} ${active ? styles.navItemActive : ""}`}
    >
      <span className={styles.navIcon}>{icon}</span>
      <span>{label}</span>
      {trailing}
    </Link>
  );
}

function WorkspaceNavigation({
  workspaceBase,
  pathname,
  mobile = false,
}: {
  mobile?: boolean;
  workspaceBase: string | null;
  pathname: string;
}) {
  const { t } = useLocale();
  const { summary } = useChatUnread();
  const dashboardItem = (<NavItem href={workspaceBase ? `${workspaceBase}/dashboard` : "/dashboard"}
        label={t("Dashboard", "داشبورد")} active={pathname === `${workspaceBase}/dashboard`} icon={<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 3h5v5H3zM12 3h5v5h-5zM3 12h5v5H3zM12 12h5v5h-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>} />);
  return (
    <>
      {!mobile && dashboardItem}
      <NavItem
        href={workspaceBase ? `${workspaceBase}/projects` : null}
        label={t("Projects", "پروژه‌ها")}
        active={pathname.startsWith(`${workspaceBase}/projects`)}
        icon={<svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M2 5a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5Z"
            stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        </svg>}
      />
      <NavItem
        href={workspaceBase ? `${workspaceBase}/calendar` : null}
        label={t("Calendar", "تقویم")}
        active={pathname === `${workspaceBase}/calendar`}
        icon={<CalendarIcon />}
      />
      {mobile && dashboardItem}
      <NavItem href={workspaceBase ? `${workspaceBase}/chats` : null}
        label={t("Chats", "گفت‌وگوها")} active={pathname === `${workspaceBase}/chats`} icon={<ChatIcon />} trailing={<span className={styles.chatBadge}><ChatUnreadBadge count={summary.unread_count} /></span>} />
      {!mobile && <WorkspaceManagementNavigation workspaceBase={workspaceBase} pathname={pathname} />}
    </>
  );
}

function WorkspaceManagementNavigation({ workspaceBase, pathname }: {
  workspaceBase: string | null;
  pathname: string;
}) {
  const { t } = useLocale();
  return (
    <>
      <NavItem href={workspaceBase ? `${workspaceBase}/reports` : null}
        label={t("Reports", "گزارش‌ها")} active={pathname === `${workspaceBase}/reports`} icon={<ReportIcon />} />
      <NavItem href={workspaceBase ? `${workspaceBase}/members` : null}
        label={t("People", "اعضا")}
        active={pathname === `${workspaceBase}/members` || pathname === `${workspaceBase}/invitations`}
        icon={<DesignIcon name="users" />} />
      <NavItem href={workspaceBase ? `${workspaceBase}/settings` : null}
        label={t("Settings", "تنظیمات")} active={pathname === `${workspaceBase}/settings`}
        icon={<DesignIcon name="settings" />} />
    </>
  );
}

function getInitials(firstName: string, lastName: string) {
  const first = firstName.trim().charAt(0);
  const last = lastName.trim().charAt(0);

  return `${first}${last}`.toUpperCase() || "U";
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <NotificationCountProvider>
      <DashboardShell>{children}</DashboardShell>
    </NotificationCountProvider>
  );
}

function DashboardShell({ children }: DashboardLayoutProps) {
  const { t, formatNumber } = useLocale();
  const { count } = useNotificationCount();
  const moreMenu = useRef<HTMLDetailsElement>(null);
  const moreTrigger = useRef<HTMLElement>(null);
  const inbox = "/dashboard/notifications";
  const unread = t(`${formatNumber(count ?? 0)} unread`, `${formatNumber(count ?? 0)} خوانده‌نشده`);
  const notificationsLabel = count
    ? t(`Notifications, ${unread}`, `اعلان‌ها، ${unread}`)
    : t("Notifications", "اعلان‌ها");
  const badge = count ? (
    <span className={styles.notificationBadge} aria-hidden="true">
      {count > 99 ? `${formatNumber(99)}+` : formatNumber(count)}
    </span>
  ) : null;
  const pathname = usePathname();
  const { slug: routeSlug } = useParams<{ slug?: string }>();
  const [activeWorkspace, setActiveWorkspace] = useState<{
    userId: number;
    slug: string;
  } | null>(null);
  const router = useRouter();
  const { user, accessToken, isAuthenticated, isLoading, logout } = useAuth();
  const userId = user?.id;
  const slug =
    routeSlug ||
    (activeWorkspace?.userId === userId ? activeWorkspace?.slug : undefined);
  const workspaceBase = slug
    ? "/dashboard/workspaces/" + encodeURIComponent(slug)
    : null;

  useEffect(() => {
    if (!accessToken || userId === undefined) return;
    let cancelled = false;
    const key = dashboardWorkspaceKey(userId);
    let savedSlug: string | null = null;
    try {
      savedSlug = localStorage.getItem(key) || sessionStorage.getItem(key);
    } catch {}
    loadDashboardWorkspace(accessToken, routeSlug, savedSlug)
      .then((workspace) => {
        if (cancelled) return;
        setActiveWorkspace(workspace ? { userId, slug: workspace.slug } : null);
        try {
          if (workspace) {sessionStorage.setItem(key, workspace.slug); localStorage.setItem(key, workspace.slug);}
          else {sessionStorage.removeItem(key); localStorage.removeItem(key);}
        } catch {}
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [accessToken, userId, routeSlug]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (moreMenu.current) moreMenu.current.open = false;
  }, [pathname]);

  if (isLoading || !isAuthenticated || !user) {
    return null;
  }

  if (pathname === "/dashboard") return <main>{children}</main>;

  const initials = getInitials(user.first_name, user.last_name);

  const isProfile = pathname === "/dashboard/profile";
  const isSecurity = pathname === "/dashboard/security";
  const isSessions = pathname === "/dashboard/sessions";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <ChatUnreadProvider slug={slug}>
    <div className={styles.dashboard}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <DashboardBrand />

          <WorkspaceSwitcher slug={slug} />

          <nav className={styles.navigation} aria-label={t("Workspace", "فضای کاری")}>
            <div className={styles.sectionLabel}>{t("WORKSPACE", "فضای کاری")}</div>

            <WorkspaceNavigation
              workspaceBase={workspaceBase}
              pathname={pathname}
            />
            <NavItem
              href={inbox}
              label={t("Notifications", "اعلان‌ها")}
              active={pathname === inbox}
              icon={<BellIcon />}
              trailing={badge}
              accessibleLabel={notificationsLabel}
            />
            <div className={styles.sectionLabel}>{t("ACCOUNT", "حساب کاربری")}</div>

            <NavItem
              href="/dashboard/profile"
              label={t("Profile", "نمایه")}
              active={isProfile}
              icon={<UserIcon />}
            />

            <NavItem
              href="/dashboard/security"
              label={t("Security", "امنیت")}
              active={isSecurity}
              icon={<LockIcon />}
            />

            <NavItem
              href="/dashboard/sessions"
              label={t("Sessions", "نشست‌ها")}
              active={isSessions}
              icon={<MonitorIcon />}
            />
          </nav>
        </div>

        <div className={styles.sidebarBottom}>
          <PreferencesControls compact />
          <button
            type="button"
            className={styles.signOutButton}
            onClick={handleLogout}
          >
            <span className={styles.navIcon}>
              <LogoutIcon />
            </span>
            <span>{t("Sign out", "خروج از حساب")}</span>
          </button>

          <div className={styles.userSummary}>
            <Avatar
              className={styles.smallAvatar}
              src={user.avatar}
              fallback={initials}
            />

            <div className={styles.userSummaryText}>
              <div className={styles.userName} dir="auto">
                {user.first_name} {user.last_name}
              </div>
              <div className={styles.userEmail}><bdi>{user.email}</bdi></div>
            </div>
          </div>
        </div>
      </aside>

      <header className={styles.mobileHeader}>
        <DashboardBrand />
        <div className={styles.mobileHeaderActions}>
          <PreferencesControls compact />
          <Link
            href={inbox}
            className={styles.mobileLogoutButton}
            aria-label={notificationsLabel}
            aria-current={pathname === inbox ? "page" : undefined}
          >
            <BellIcon />
            {badge}
          </Link>
        </div>
        <div className={styles.mobileWorkspace}>
          <WorkspaceSwitcher slug={slug} mobile />
          {workspaceBase && (
            <details ref={moreMenu} className={styles.mobileMore}
              onKeyDown={(event) => {
                if (event.key === "Escape" && event.currentTarget.open) {
                  event.currentTarget.open = false;
                  moreTrigger.current?.focus();
                }
              }}>
              <summary ref={moreTrigger}>
                {t("More", "بیشتر")}
                <span aria-hidden="true">⌄</span>
              </summary>
              <nav className={styles.moreItems} aria-label={t("Workspace options", "گزینه‌های فضای کاری")}>
                <WorkspaceManagementNavigation workspaceBase={workspaceBase} pathname={pathname} />
              </nav>
            </details>
          )}
        </div>
      </header>

      <main className={styles.main}>
        {(isProfile || isSecurity || isSessions) && (
          <nav
            className={styles.mobileAccountNav}
            aria-label={t("Account navigation", "ناوبری حساب کاربری")}
          >
            <NavItem
              href="/dashboard/profile"
              label={t("Profile", "نمایه")}
              active={isProfile}
              icon={<UserIcon />}
            />
            <NavItem
              href="/dashboard/security"
              label={t("Security", "امنیت")}
              active={isSecurity}
              icon={<LockIcon />}
            />
            <NavItem
              href="/dashboard/sessions"
              label={t("Sessions", "نشست‌ها")}
              active={isSessions}
              icon={<MonitorIcon />}
            />
            <button
              className={styles.signOutButton}
              onClick={handleLogout}
              aria-label={t("Sign out", "خروج از حساب")}
            >
              <LogoutIcon />
            </button>
          </nav>
        )}
        {children}
      </main>

      <nav className={styles.mobileTabBar} aria-label={t("Dashboard", "داشبورد")}>
        <WorkspaceNavigation mobile
          workspaceBase={workspaceBase}
          pathname={pathname}
        />
        <NavItem
          href="/dashboard/profile"
          label={t("Account", "حساب کاربری")}
          active={isProfile || isSecurity || isSessions}
          icon={<UserIcon />}
        />
      </nav>
    </div>
    </ChatUnreadProvider>
  );
}
