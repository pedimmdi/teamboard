import Link from "next/link";
import { posts, publicMetadata, jsonLd, siteUrl } from "@/lib/website";
import PostList from "@/components/website/post-list";
import { HomeSession } from "@/components/website/public-auth";
import styles from "./website.module.css";
export const metadata = publicMetadata(
  "TeamBoard — Plan work. Ship together.",
  "Organize projects, discuss tasks, and stay on top of deadlines with TeamBoard’s shared workspace.",
  "/",
);
export default async function Home() {
  const articles = await posts().catch(() => null);
  return (
    <>
      <HomeSession />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            name: "TeamBoard",
            url: siteUrl,
            applicationCategory: "BusinessApplication",
            operatingSystem: "Web",
            description:
              "Projects, tasks and conversations in one shared workspace.",
          }),
        }}
      />
      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>
            ONE WORKSPACE. A CLEARER WAY TO WORK.
          </p>
          <h1>
            Plan work.
            <br />
            Ship together.
          </h1>
          <p>
            Bring your projects, conversations and deadlines into one shared
            place. Know what needs your attention, and keep your team moving
            forward.
          </p>
          <div className={styles.actions}>
            <Link className={styles.primary} href="/register">
              Create your account →
            </Link>
            <Link className={styles.secondary} href="/about">
              Explore TeamBoard
            </Link>
          </div>
          <small>Built around your team. Focused on your next step.</small>
        </div>
        <div
          className={styles.preview}
          aria-label="Example TeamBoard dashboard"
        >
          <div className={styles.previewTop}>
            ▥ TeamBoard <span>Product team</span>
          </div>
          <div className={styles.previewBody}>
            <small>WORKSPACE / DASHBOARD</small>
            <h2>Your work, at a glance.</h2>
            <div className={styles.stats}>
              <div>
                Today<strong>4</strong>
              </div>
              <div>
                Follow up<strong>2</strong>
              </div>
              <div>
                Due soon<strong>6</strong>
              </div>
            </div>
            <div className={styles.sample}>
              <strong>My Tasks</strong>
              <p>
                Design the next release <span>In progress</span>
              </p>
              <p>
                Review onboarding <span>To do</span>
              </p>
              <p>
                Share release notes <span>In review</span>
              </p>
            </div>
            <small>Illustrative workspace · sample data</small>
          </div>
        </div>
      </section>
      <section className={styles.section}>
        <p className={styles.eyebrow}>LESS CONTEXT SWITCHING. MORE PROGRESS.</p>
        <h2>Everything your team needs to move work forward.</h2>
        <div className={styles.cards}>
          {[
            [
              "Projects that stay organized",
              "Keep ownership clear with workspaces, project roles and task boards.",
            ],
            [
              "Conversations in context",
              "Discuss tasks, reply to teammates and share files where the work happens.",
            ],
            [
              "Deadlines you can see",
              "Plan with calendars, set private reminders and keep track of upcoming work.",
            ],
            [
              "A clear view of progress",
              "See personal priorities on your dashboard and explore reports when you need more detail.",
            ],
          ].map(([title, body]) => (
            <article className={styles.card} key={title}>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>
      <section className={styles.section}>
        <div className={styles.sectionTitle}>
          <div>
            <p className={styles.eyebrow}>FROM THE TEAMBOARD BLOG</p>
            <h2>Ideas for better teamwork.</h2>
          </div>
          <Link href="/blog">All articles →</Link>
        </div>
        {articles?.results.length ? (
          <PostList items={articles.results.slice(0, 3)} />
        ) : (
          <p>
            {articles
              ? "Our first articles are on their way. Check back soon."
              : "Articles are temporarily unavailable. Visit the blog to try again."}
          </p>
        )}
      </section>
      <section className={styles.cta}>
        <h2>Make room for your best work.</h2>
        <p>Your projects and teammates, brought together.</p>
        <Link className={styles.primary} href="/register">
          Get started with TeamBoard
        </Link>
      </section>
    </>
  );
}
