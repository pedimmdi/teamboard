import { AuthEntry } from "@/components/website/public-auth";
import { WebsiteIcon } from "@/components/website/website-icons";
import { getLocale } from "@/lib/server-preferences";
import { publicMetadata } from "@/lib/website";
import { websiteCopy } from "@/lib/website-copy";
import styles from "../website.module.css";

const icons = ["board", "chat", "reports"] as const;

export async function generateMetadata() {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return publicMetadata(locale === "fa" ? "درباره تیم‌برد" : "About TeamBoard", copy.aboutDescription, "/about", locale);
}

export default async function About() {
  const locale = await getLocale();
  const copy = websiteCopy[locale];
  return (
    <article>
      <header className={styles.masthead}>
        <div>
          <p className={styles.eyebrow}>{copy.about}</p>
          <h1>{copy.aboutTitle}</h1>
          <p>{copy.aboutDescription}</p>
        </div>
      </header>
      <section className={styles.section}>
        <div className={styles.aboutRows}>
          {copy.aboutSections.map(([title, body], index) => (
            <div key={title}>
              <span className={styles.featureIcon}><WebsiteIcon name={icons[index]} /></span>
              <h2>{title}</h2>
              <p>{body}</p>
            </div>
          ))}
        </div>
        <div className={styles.cta}>
          <h2>{copy.cta}</h2>
          <AuthEntry className={styles.primary} href="/register" locale={locale}>{copy.heroAction}<WebsiteIcon name="arrow" className={styles.arrow} /></AuthEntry>
        </div>
      </section>
    </article>
  );
}
