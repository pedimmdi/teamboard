import type { MetadataRoute } from "next";
import { languageUrls, siteUrl, websitePath } from "@/lib/website";
import { createSitemapReader } from "@/lib/website-cache";
import { sitemapPage } from "@/lib/website-data";

export const dynamic = "force-dynamic";

function localizedEntries(path: string, hasTranslation = true, lastModified?: string): MetadataRoute.Sitemap {
  const alternates = hasTranslation ? { languages: Object.fromEntries(
    Object.entries(languageUrls(path)).map(([locale, localPath]) => [locale, siteUrl + localPath]),
  ) } : undefined;
  const locales = hasTranslation ? ["en", "fa"] as const : ["en"] as const;
  return locales.map((locale) => ({
    url: siteUrl + websitePath(path, locale),
    alternates,
    lastModified,
  }));
}

const coreEntries = ["/", "/about", "/contact", "/blog", "/privacy", "/terms"].flatMap((path) => localizedEntries(path));

const articleEntries = createSitemapReader(async () => {
  const signal = AbortSignal.timeout(10_000);
  const entries: MetadataRoute.Sitemap = [];
  const seen = new Set<string>();
  let cursor: string | undefined;
  do {
    const data = await sitemapPage(cursor, signal);
    for (const item of data.results) {
      entries.push(...localizedEntries(`/blog/${encodeURIComponent(item.slug)}`, item.has_persian_translation, item.updated_at ?? item.published_at));
    }
    if (entries.length + coreEntries.length > 50_000) throw new Error("Sitemap exceeds a single file; configure a sitemap index.");
    if (!data.next) return entries;
    const next = new URL(data.next).searchParams.get("cursor");
    if (!next || seen.has(next) || !data.results.length) throw new Error("Invalid sitemap pagination.");
    seen.add(next);
    cursor = next;
  } while (cursor);
  return entries;
}, []);

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  return [...coreEntries, ...await articleEntries()];
}
