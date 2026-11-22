import { publicMetadata } from "@/lib/website";
import ContactForm from "@/components/website/contact-form";
import styles from "../website.module.css";
export const metadata = publicMetadata(
  "Contact TeamBoard",
  "Get in touch with TeamBoard. Send a question or share feedback about your workspace.",
  "/contact",
);
export default function Contact() {
  return (
    <section className={styles.document}>
      <p className={styles.eyebrow}>LET’S TALK</p>
      <h1>How can we help?</h1>
      <p>
        Ask a question or tell us how TeamBoard could work better for your team.
        Please don’t include passwords or other sensitive information.
      </p>
      <ContactForm />
    </section>
  );
}
