import Link from "next/link";
import { Suspense } from "react";
import { PublicStart } from "@/components/website/public-auth";
import PostList from "@/components/website/post-list";
import BrandMark from "@/components/ui/BrandMark";
import { WebsiteIcon } from "@/components/website/website-icons";
import { getLocale } from "@/lib/server-preferences";
import { jsonLd, publicMetadata, siteUrl, websitePath, type WebsiteLocale } from "@/lib/website";
import { posts } from "@/lib/website-data";
import { websiteCopy } from "@/lib/website-copy";
import styles from "./website.module.css";

const featureIcons = ["board", "chat", "calendar", "reports"] as const;

export async function generateMetadata() {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return publicMetadata(copy.homeTitle, copy.homeDescription, "/", locale);
}

function WorkspacePreview({ locale }: { locale: WebsiteLocale }) {
  const copy = websiteCopy[locale];
  const numbers = new Intl.NumberFormat(locale);
  return (
    <div className={styles.previewStage}>
      <figure className={styles.preview} role="img" aria-label={copy.preview}>
        <div aria-hidden="true">
          <div className={styles.previewBar}>
            <span className={styles.previewBrand}><BrandMark /> {locale === "fa" ? "تیم‌برد" : "TeamBoard"}</span>
            <span className={styles.previewTeam}>{copy.previewTeam}</span>
            <div className={styles.people}><span>JD</span><span>AR</span><span>SL</span></div>
          </div>
          <div className={styles.previewBody}>
            <div className={styles.previewHeading}>{copy.previewHeading}</div>
            <div className={styles.previewTabs}>{copy.previewTabs.map((tab) => <span key={tab}>{tab}</span>)}</div>
            <div className={styles.board}>
              {copy.previewStatuses.map((status, index) => (
                <div key={status} className={styles.column}>
                  <div className={styles.columnLabel}><i />{status}<small>{numbers.format(1)}</small></div>
                  <div className={styles.boardCard}>
                    <small>{copy.previewTags[index]}</small>
                    <strong>{copy.previewTasks[index]}</strong>
                    <div className={styles.boardCardFooter}>
                      <span>{["AR", "JD", "SL"][index]}</span>
                      {index === 2 && <WebsiteIcon name="check" width="15" height="15" />}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </figure>
    </div>
  );
}

async function LatestArticles({ locale }: { locale: WebsiteLocale }) {
  const copy = websiteCopy[locale];
  const articles = await posts(1, 3, locale).catch(() => null);
  if (!articles) return <p>{copy.unableArticles}</p>;
  if (!articles.results.length) return <p>{copy.noArticles}</p>;
  return <PostList items={articles.results} locale={locale} headingLevel={3} />;
}

export default async function Home() {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  const homeUrl = siteUrl + websitePath("/", locale);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@graph": [
              { "@type": "Organization", "@id": siteUrl + "/#organization", name: "TeamBoard", url: siteUrl, logo: siteUrl + "/icon.svg" },
              { "@type": "WebSite", name: "TeamBoard", url: homeUrl, inLanguage: locale, publisher: { "@id": siteUrl + "/#organization" } },
              { "@type": "WebApplication", name: "TeamBoard", url: homeUrl, inLanguage: locale, applicationCategory: "BusinessApplication", operatingSystem: "Web", description: copy.homeDescription },
            ],
          }),
        }}
      />
      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div className={styles.heroCopy}>
            <h1>{copy.heroLead} <span>{copy.heroEnd}</span></h1>
            <p>{copy.heroBody}</p>
            <div className={styles.actions}>
              <PublicStart locale={locale}>{copy.heroAction}<WebsiteIcon name="arrow" className={styles.arrow} /></PublicStart>
              <Link className={styles.secondary} href={websitePath("/about", locale)} prefetch={false}>{copy.explore}</Link>
            </div>
          </div>
          <WorkspacePreview locale={locale} />
        </div>
      </section>
      <section className={styles.section}>
        <h2>{copy.featureHeading}</h2>
        <div className={styles.features}>
          {copy.features.map(([title, body], index) => (
            <article key={title}>
              <span className={styles.featureIcon}><WebsiteIcon name={featureIcons[index]} /></span>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>
      <section className={styles.blogBand}>
        <div className={styles.section}>
          <div className={styles.sectionTitle}>
            <h2>{copy.latestArticles}</h2>
            <Link className={styles.textLink} href={websitePath("/blog", locale)} prefetch={false}>{copy.allArticles}<WebsiteIcon name="arrow" className={styles.arrow} /></Link>
          </div>
          <Suspense fallback={<p role="status">{copy.loadingArticles}</p>}>
            <LatestArticles locale={locale} />
          </Suspense>
        </div>
      </section>
      <section className={styles.section}>
        <div className={styles.cta}>
          <h2>{copy.cta}</h2>
          <PublicStart locale={locale}>{copy.heroAction}<WebsiteIcon name="arrow" className={styles.arrow} /></PublicStart>
        </div>
      </section>
    </>
  );
}
