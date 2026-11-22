import type { MetadataRoute } from "next";
import { languageUrls, posts, siteUrl, websitePath } from "@/lib/website";

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

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries = ["/", "/about", "/contact", "/blog", "/privacy", "/terms"].flatMap((path) => localizedEntries(path));
  const firstPage = await posts(1, 50).catch(() => null);
  if (!firstPage) return entries;

  let page = 1;
  let data = firstPage;
  do {
    for (const item of data.results) {
      entries.push(...localizedEntries(`/blog/${encodeURIComponent(item.slug)}`, item.has_persian_translation, item.updated_at ?? item.published_at));
    }
    if (entries.length > 50000) throw new Error("Sitemap exceeds a single file; configure a sitemap index.");
    if (!data.next) return entries;
    data = await posts(++page, 50);
  } while (data.results.length);
  return entries;
}
