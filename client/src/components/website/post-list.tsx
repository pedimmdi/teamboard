import Link from "next/link";
import { WebsiteIcon } from "@/components/website/website-icons";
import { websiteDate, websitePath, type Post, type WebsiteLocale } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import styles from "@/app/(public)/website.module.css";

export default function PostList({ items, locale, headingLevel = 2 }: {
  items: Post[];
  locale: WebsiteLocale;
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <div className={styles.cards}>
      {items.map((item) => (
        <article className={styles.card} key={item.id}>
          <time dateTime={item.published_at}>{websiteDate(item.published_at, locale)}</time>
          <Heading>
            <Link className={styles.cardLink} href={websitePath(`/blog/${encodeURIComponent(item.slug)}`, locale)}>{item.title}</Link>
          </Heading>
          {item.excerpt && <p>{item.excerpt}</p>}
          <span className={styles.cardPrompt} aria-hidden="true">{websiteCopy[locale].readArticle}<WebsiteIcon name="arrow" className={styles.arrow} /></span>
        </article>
      ))}
    </div>
  );
}
