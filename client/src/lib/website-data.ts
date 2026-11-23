import "server-only";
import type { Post, WebsiteLocale } from "@/lib/website";
import { createTimedReadCache } from "@/lib/website-cache";

type BlogListing = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Post[];
};

type SitemapEntry = Pick<Post, "slug" | "published_at" | "updated_at" | "has_persian_translation">;
type SitemapPage = { results: SitemapEntry[]; next: string | null };
type WebsitePolicy = { contact_retention_days: number };

const readListing = createTimedReadCache<BlogListing>(60_000, 64);
const readArticle = createTimedReadCache<Post>(30_000, 128);
const readPolicy = createTimedReadCache<WebsitePolicy>(60_000, 1);

async function publicRead<T>(path: string, signal = AbortSignal.timeout(10_000)): Promise<T> {
  const base = process.env.WEBSITE_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${base.replace(/\/$/, "")}/api/v1/website/${path}`, {
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    signal,
  });
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}

export function posts(page = 1, pageSize = 10, locale: WebsiteLocale = "en") {
  const path = `blog/?page=${page}&page_size=${pageSize}&lang=${locale}`;
  return readListing(path, () => publicRead<BlogListing>(path));
}

export function post(slug: string, locale: WebsiteLocale) {
  const path = `blog/${encodeURIComponent(slug)}/?lang=${locale}`;
  return readArticle(path, () => publicRead<Post>(path));
}

export function sitemapPage(cursor: string | undefined, signal: AbortSignal) {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return publicRead<SitemapPage>(`sitemap/${query}`, signal);
}

export async function contactRetentionDays(): Promise<number | null> {
  try {
    const { contact_retention_days: days } = await readPolicy("policy", () => publicRead<WebsitePolicy>("policy/", AbortSignal.timeout(2_000)));
    return Number.isInteger(days) && days >= 1 && days <= 3650 ? days : null;
  } catch {
    return null;
  }
}
