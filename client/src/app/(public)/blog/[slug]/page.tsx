import { cache } from "react";
import Link from "next/link";
import Markdown from "react-markdown";
import { notFound } from "next/navigation";
import { WebsiteIcon } from "@/components/website/website-icons";
import { getLocale } from "@/lib/server-preferences";
import { articleDescription, publicMetadata, jsonLd, siteUrl, websitePath, websiteDate } from "@/lib/website";
import { post } from "@/lib/website-data";
import { websiteCopy } from "@/lib/website-copy";
import styles from "../../website.module.css";

const read = cache(post);
type ArticleProps = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: ArticleProps) {
  const [locale, { slug }] = await Promise.all([getLocale(), params]);
  try {
    const item = await read(slug, locale);
    const translated = item.has_persian_translation;
    const defaultLocale = locale === "fa" && !translated ? "en" : locale;
    const description = articleDescription(item.title, item.excerpt, defaultLocale);
    const canonical = `/blog/${encodeURIComponent(item.slug)}`;
    const metadata = publicMetadata(item.title, description, canonical, defaultLocale, translated);
    return {
      ...metadata,
      robots: defaultLocale === locale ? undefined : { index: false, follow: true },
      openGraph: {
        ...metadata.openGraph,
        type: "article" as const,
        publishedTime: item.published_at,
        modifiedTime: item.updated_at,
      },
    };
  } catch {
    return { title: websiteCopy[locale].articleUnavailable, robots: { index: false } };
  }
}

export default async function Article({ params }: ArticleProps) {
  const [locale, { slug }] = await Promise.all([getLocale(), params]);
  const copy = websiteCopy[locale];
  const item = await read(slug, locale).catch((error: Error) => {
    if (error.message === "404") notFound();
    throw error;
  });
  const fallback = locale === "fa" && !item.has_persian_translation;
  const contentLocale = fallback ? "en" : locale;
  const articleUrl = siteUrl + websitePath(`/blog/${encodeURIComponent(item.slug)}`, contentLocale);
  const blogUrl = websitePath("/blog", locale);

  return (
    <article className={styles.document}>
      {!fallback && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: jsonLd({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "BlogPosting",
                  headline: item.title,
                  description: articleDescription(item.title, item.excerpt, contentLocale),
                  image: siteUrl + "/opengraph-image",
                  datePublished: item.published_at,
                  dateModified: item.updated_at,
                  mainEntityOfPage: articleUrl,
                  inLanguage: contentLocale,
                  publisher: { "@type": "Organization", name: "TeamBoard", url: siteUrl },
                },
                {
                  "@type": "BreadcrumbList",
                  itemListElement: [
                    { "@type": "ListItem", position: 1, name: copy.blog, item: siteUrl + blogUrl },
                    { "@type": "ListItem", position: 2, name: item.title, item: articleUrl },
                  ],
                },
              ],
            }),
          }}
        />
      )}
      <Link className={styles.textLink} href={blogUrl}><WebsiteIcon name="arrow" className={styles.directionBack} />{copy.backToBlog}</Link>
      {fallback && <p className={styles.notice}>{copy.noTranslation}</p>}
      <div lang={contentLocale} dir={contentLocale === "fa" ? "rtl" : "ltr"}>
        <header className={styles.documentHeading}>
          <h1>{item.title}</h1>
          <time dateTime={item.published_at}>{websiteDate(item.published_at, contentLocale)}</time>
          {item.excerpt && <p>{item.excerpt}</p>}
        </header>
        <div className={styles.markdown}>
          <Markdown skipHtml components={{ img: ({ alt }) => <span>{alt}</span> }}>{item.content ?? ""}</Markdown>
        </div>
      </div>
    </article>
  );
}
