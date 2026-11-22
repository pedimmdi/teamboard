import { cache } from "react";
import Markdown from "react-markdown";
import { notFound } from "next/navigation";
import { post, publicMetadata, jsonLd, siteUrl } from "@/lib/website";
import styles from "../../website.module.css";
const read = cache(post);
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  try {
    const item = await read(slug);
    return {
      ...publicMetadata(
        item.title,
        item.excerpt,
        `/blog/${encodeURIComponent(slug)}`,
      ),
      openGraph: {
        title: item.title,
        description: item.excerpt,
        type: "article",
        publishedTime: item.published_at,
        modifiedTime: item.updated_at,
      },
    };
  } catch {
    return { title: "Article unavailable", robots: { index: false } };
  }
}
export default async function Article({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let item;
  try {
    item = await read(slug);
  } catch (error) {
    if (error instanceof Error && error.message === "404") notFound();
    throw error;
  }
  return (
    <article className={styles.document}>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            headline: item.title,
            description: item.excerpt,
            datePublished: item.published_at,
            dateModified: item.updated_at,
            mainEntityOfPage: `${siteUrl}/blog/${encodeURIComponent(item.slug)}`,
            publisher: {
              "@type": "Organization",
              name: "TeamBoard",
              url: siteUrl,
            },
          }),
        }}
      />
      <p className={styles.eyebrow}>TEAMBOARD BLOG</p>
      <h1>{item.title}</h1>
      <time dateTime={item.published_at}>
        {new Date(item.published_at).toLocaleDateString("en", {
          timeZone: "UTC",
          dateStyle: "long",
        })}
      </time>
      <p>{item.excerpt}</p>
      <div className={styles.markdown}>
        <Markdown
          skipHtml
          components={{ img: ({ alt }) => <span>{alt}</span> }}
        >
          {item.content ?? ""}
        </Markdown>
      </div>
    </article>
  );
}
