import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale } from "@/lib/server-preferences";
import { posts, publicMetadata, websitePath } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import PostList from "@/components/website/post-list";
import { WebsiteIcon } from "@/components/website/website-icons";
import styles from "../website.module.css";

type BlogPageProps = { searchParams: Promise<{ page?: string | string[] }> };

function currentPage(value: string | string[] | undefined) {
  const page = Number(value);
  return typeof value === "string" && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(page) ? page : 1;
}

function blogPath(page: number) {
  return page > 1 ? `/blog?page=${page}` : "/blog";
}

export async function generateMetadata({ searchParams }: BlogPageProps) {
  const [locale, { page }] = await Promise.all([getLocale(), searchParams]);
  const copy = websiteCopy[locale];
  const count = currentPage(page);
  const title = locale === "fa" ? "وبلاگ تیم‌برد" : "TeamBoard Blog";
  const number = new Intl.NumberFormat(locale).format(count);
  const paginated = locale === "fa" ? ` — صفحه ${number}` : ` — Page ${number}`;
  return publicMetadata(count === 1 ? title : title + paginated, copy.blogDescription, blogPath(count), locale, count === 1);
}

export default async function Blog({ searchParams }: BlogPageProps) {
  const [locale, query] = await Promise.all([getLocale(), searchParams]);
  const copy = websiteCopy[locale];
  const page = currentPage(query.page);
  const data = await posts(page, 10, locale).catch((error: Error) => {
    if (error.message === "404" && page > 1) notFound();
    return null;
  });
  const numbers = new Intl.NumberFormat(locale);
  const pageLabel = locale === "fa"
    ? `صفحه ${numbers.format(page)} · ${numbers.format(data?.count ?? 0)} نوشته`
    : `Page ${numbers.format(page)} · ${numbers.format(data?.count ?? 0)} ${data?.count === 1 ? "article" : "articles"}`;
  return (
    <>
      <header className={styles.masthead}>
        <div>
          <p className={styles.eyebrow}>{locale === "fa" ? "وبلاگ تیم‌برد" : "TeamBoard Blog"}</p>
          <h1>{copy.blogHeading}</h1>
          <p>{copy.blogDescription}</p>
        </div>
      </header>
      <section className={styles.section}>
        {!data ? (
          <div role="alert">
            <p>{copy.unableArticles}</p>
            <Link className={styles.textLink} href={websitePath(blogPath(page), locale)}>{copy.retry}</Link>
          </div>
        ) : data.results.length === 0 ? <p>{copy.noArticles}</p> : (
          <>
            <PostList items={data.results} locale={locale} />
            {(data.previous || data.next) && (
              <nav className={styles.pagination} aria-label={copy.pagination}>
                {data.previous && <Link rel="prev" href={websitePath(blogPath(page - 1), locale)} aria-label={locale === "en" ? "← Previous" : undefined}><WebsiteIcon name="arrow" className={styles.directionBack} width="16" height="16" />{copy.previous}</Link>}
                <span>{pageLabel}</span>
                {data.next && <Link rel="next" href={websitePath(blogPath(page + 1), locale)} aria-label={locale === "en" ? "Next →" : undefined}>{copy.next}<WebsiteIcon name="arrow" className={styles.arrow} width="16" height="16" /></Link>}
              </nav>
            )}
          </>
        )}
      </section>
    </>
  );
}
