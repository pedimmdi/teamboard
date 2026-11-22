import type { MetadataRoute } from "next";
import { posts, siteUrl } from "@/lib/website";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    "",
    "/about",
    "/contact",
    "/blog",
    "/privacy",
    "/terms",
  ].map((path) => ({ url: siteUrl + path }));
  let page = 1;
  while (page <= 1000) {
    const data = await posts(page, 50);
    for (const item of data.results)
      entries.push({
        url: `${siteUrl}/blog/${encodeURIComponent(item.slug)}`,
        lastModified: new Date(item.published_at),
      });
    if (!data.next) return entries;
    page++;
  }
  throw new Error("Sitemap exceeds a single file; configure a sitemap index.");
}
