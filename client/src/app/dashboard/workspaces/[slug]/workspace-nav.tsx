"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./workspace-nav.module.css";

type Props = {
  slug: string;
};

export default function WorkspaceNav({ slug }: Props) {
  const { ui } = useWorkspaceLocale();
  const pathname = usePathname();

  const basePath = `/dashboard/workspaces/${encodeURIComponent(slug)}`;

  const items = [
    { label: "Dashboard", href: `${basePath}/dashboard` },
    { label: "Projects", href: `${basePath}/projects` },
    { label: "Calendar", href: `${basePath}/calendar` },
    { label: "Chats", href: `${basePath}/chats` },
    { label: "Reports", href: `${basePath}/reports` },
    { label: "Members", href: `${basePath}/members` },
    { label: "Invitations", href: `${basePath}/invitations` },
    { label: "Settings", href: `${basePath}/settings` },
  ];

  return (
    <nav aria-label={ui("Workspace navigation")} className={styles.nav}>
      {items.map((item) => {
        const isActive = pathname === item.href;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={`${styles.link} ${
              isActive ? styles.active : ""
            }`}
          >
            {ui(item.label)}
          </Link>
        );
      })}
    </nav>
  );
}
