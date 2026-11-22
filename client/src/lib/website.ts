import type { Metadata } from "next";

export type WebsiteLocale = "en" | "fa";

export type Post = {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  published_at: string;
  updated_at?: string;
  content?: string;
  has_persian_translation: boolean;
};

export function websitePath(path: string, locale: WebsiteLocale) {
  return locale === "fa" ? `/fa${path === "/" ? "" : path}` : path;
}

export function languageUrls(path: string) {
  return { en: websitePath(path, "en"), fa: websitePath(path, "fa"), "x-default": path };
}

export function websiteDate(value: string, locale: WebsiteLocale) {
  return new Intl.DateTimeFormat(locale, { timeZone: "UTC", dateStyle: "long" }).format(new Date(value));
}
export function jsonLd(value: Record<string, unknown>) {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
export const siteUrl = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"
).replace(/\/$/, "");
export async function publicRead<T>(path: string): Promise<T> {
  const base =
    process.env.WEBSITE_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  const response = await fetch(`${base}/api/v1/website/${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}
export function posts(page = 1, pageSize = 10, locale: WebsiteLocale = "en") {
  return publicRead<{
    count: number;
    next: string | null;
    previous: string | null;
    results: Post[];
  }>(`blog/?page=${page}&page_size=${pageSize}&lang=${locale}`);
}
export function post(slug: string, locale: WebsiteLocale) {
  return publicRead<Post>(`blog/${encodeURIComponent(slug)}/?lang=${locale}`);
}
export function publicMetadata(
  title: string,
  description: string,
  path: string,
  locale: WebsiteLocale,
  hasAlternate = true,
): Metadata {
  const canonical = websitePath(path, locale);
  return {
    title: { absolute: /TeamBoard|تیم‌برد/.test(title) ? title : `${title} | ${locale === "fa" ? "تیم‌برد" : "TeamBoard"}` },
    description,
    alternates: { canonical, languages: hasAlternate ? languageUrls(path) : undefined },
    openGraph: {
      title,
      description,
      url: canonical,
      type: "website",
      siteName: "TeamBoard",
      locale: locale === "fa" ? "fa_IR" : "en_US",
      alternateLocale: hasAlternate ? [locale === "fa" ? "en_US" : "fa_IR"] : undefined,
      images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "TeamBoard" }],
    },
    twitter: { card: "summary_large_image", title, description, images: ["/opengraph-image"] },
  };
}
