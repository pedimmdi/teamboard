import Link from "next/link";
import { posts, publicMetadata } from "@/lib/website";
import PostList from "@/components/website/post-list";
import styles from "../website.module.css";
export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page } = await searchParams;
  const current = /^[1-9]\d*$/.test(page ?? "") ? Number(page) : 1;
  return publicMetadata(
    "TeamBoard Blog — Ideas for better teamwork",
    "Read TeamBoard articles about project planning, collaboration and team workflows.",
    current > 1 ? `/blog?page=${current}` : "/blog",
  );
}
export default async function Blog({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const q = await searchParams;
  const page = /^[1-9]\d*$/.test(q.page ?? "") ? Number(q.page) : 1;
  const data = await posts(page).catch(() => null);
  return (
    <section className={styles.section}>
      <p className={styles.eyebrow}>THE TEAMBOARD BLOG</p>
      <h1>Ideas for better teamwork.</h1>
      <p>
        Practical perspectives on planning, collaboration and moving work
        forward.
      </p>
      {!data ? (
        <div role="alert">
          <p>Unable to load articles.</p>
          <Link href="/blog">Try again</Link>
        </div>
      ) : (
        <>
          {data.results.length ? (
            <PostList items={data.results} />
          ) : (
            <p>No articles yet. Check back soon.</p>
          )}
          <nav className={styles.pagination} aria-label="Blog pagination">
            {data.previous && (
              <Link href={`/blog?page=${page - 1}`}>← Previous</Link>
            )}
            <span>
              Page {page} · {data.count} articles
            </span>
            {data.next && <Link href={`/blog?page=${page + 1}`}>Next →</Link>}
          </nav>
        </>
      )}
    </section>
  );
}
