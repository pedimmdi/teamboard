import Link from "next/link";
import type { ReactNode } from "react";
import { getLocale } from "@/lib/server-preferences";
import styles from "../dashboard.module.css";

export default async function SecurityLayout({ children }: { children: ReactNode }) {
  const enabled = process.env.TEAMBOARD_MCP_UI === "1" || process.env.TEAMBOARD_MCP_LOCAL_UI === "1";
  if (!enabled) return children;
  const locale = await getLocale();
  return (
    <>
      {children}
      <div className={styles.page}>
        <div className={styles.content}>
          <Link className={styles.card} href="/dashboard/security/ai">
            {locale === "fa" ? "مدیریت اتصال‌های هوش مصنوعی" : "Manage AI connections"}
          </Link>
        </div>
      </div>
    </>
  );
}
