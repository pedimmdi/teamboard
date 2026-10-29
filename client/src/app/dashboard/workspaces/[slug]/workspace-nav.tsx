"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./workspace-nav.module.css";

type Props = {
  slug: string;
};

export default function WorkspaceNav({ slug }: Props) {
  const pathname = usePathname();

  const basePath = `/dashboard/workspaces/${encodeURIComponent(slug)}`;

  const items = [
    { label: "Overview", href: basePath },
    { label: "Members", href: `${basePath}/members` },
    { label: "Invitations", href: `${basePath}/invitations` },
    { label: "Settings", href: `${basePath}/settings` },
  ];

  return (
    <nav aria-label="Workspace navigation" className={styles.nav}>
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
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}