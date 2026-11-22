"use client";

import { usePathname } from "next/navigation";
import { PreferencesControls } from "@/components/preferences-controls";
import { websitePath, type WebsiteLocale } from "@/lib/website";

export function WebsitePreferences({ locale }: { locale: WebsiteLocale }) {
  const path = usePathname();
  const alternateHref = locale === "fa" ? path.slice(3) || "/" : websitePath(path, "fa");
  return <PreferencesControls alternateHref={alternateHref} compact />;
}
