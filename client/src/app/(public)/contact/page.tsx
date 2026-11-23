import { getLocale } from "@/lib/server-preferences";
import { publicMetadata } from "@/lib/website";
import { contactRetentionDays } from "@/lib/website-data";
import { websiteCopy } from "@/lib/website-copy";
import ContactForm from "@/components/website/contact-form";
import { WebsiteIcon } from "@/components/website/website-icons";
import styles from "../website.module.css";

export async function generateMetadata() {
  const locale = await getLocale();
  return publicMetadata(locale === "fa" ? "تماس با تیم‌برد" : "Contact TeamBoard", websiteCopy[locale].contactDescription, "/contact", locale);
}

export default async function Contact() {
  const [locale, retentionDays] = await Promise.all([getLocale(), contactRetentionDays()]);
  const copy = websiteCopy[locale];
  return (
    <section className={styles.contact}>
      <header className={styles.contactIntro}>
        <span className={styles.featureIcon}><WebsiteIcon name="inbox" /></span>
        <p className={styles.eyebrow}>{copy.contact}</p>
        <h1>{copy.contactTitle}</h1>
        <p>{copy.contactDescription}</p>
        <p className={styles.contactSafety}><WebsiteIcon name="lock" />{copy.contactSafety}</p>
      </header>
      <div className={styles.contactPane}>
        <h2>{copy.form.heading}</h2>
        <ContactForm locale={locale} retentionDays={retentionDays} />
      </div>
    </section>
  );
}
