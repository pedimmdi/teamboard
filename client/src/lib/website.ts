export type Post = {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  published_at: string;
  updated_at?: string;
  content?: string;
};
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
export function posts(page = 1, pageSize = 10) {
  return publicRead<{
    count: number;
    next: string | null;
    previous: string | null;
    results: Post[];
  }>(`blog/?page=${page}&page_size=${pageSize}`);
}
export function post(slug: string) {
  return publicRead<Post>(`blog/${encodeURIComponent(slug)}/`);
}
export function publicMetadata(
  title: string,
  description: string,
  path: string,
) {
  return {
    title: { absolute: title.includes("TeamBoard") ? title : `${title} | TeamBoard` },
    description,
    alternates: { canonical: path },
    openGraph: {
      title,
      description,
      url: path,
      type: "website" as const,
      siteName: "TeamBoard",
    },
    twitter: { card: "summary" as const, title, description },
  };
}
