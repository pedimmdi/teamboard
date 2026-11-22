import Link from "next/link";
import type { Post } from "@/lib/website";
import styles from "@/app/(public)/website.module.css";
export default function PostList({ items }: { items: Post[] }) {
  return (
    <div className={styles.cards}>
      {items.map((item) => (
        <article className={styles.card} key={item.id}>
          <time dateTime={item.published_at}>
            {new Date(item.published_at).toLocaleDateString("en", {
              year: "numeric",
              month: "long",
              day: "numeric",
              timeZone: "UTC",
            })}
          </time>
          <h2>
            <Link href={`/blog/${encodeURIComponent(item.slug)}`}>
              {item.title}
            </Link>
          </h2>
          <p>{item.excerpt}</p>
          <Link href={`/blog/${encodeURIComponent(item.slug)}`}>
            Read article →
          </Link>
        </article>
      ))}
    </div>
  );
}
