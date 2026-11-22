import { publicMetadata } from "@/lib/website";
import styles from "../website.module.css";
export const metadata = publicMetadata(
  "Terms — TeamBoard",
  "Terms for using TeamBoard’s collaboration platform and public website.",
  "/terms",
);
export default function Terms() {
  return (
    <article className={styles.document}>
      <h1>Terms of use</h1>
      <h2>Using TeamBoard</h2>
      <p>
        Use TeamBoard lawfully and respect other users. You are responsible for
        your account credentials and for content you share. Do not upload
        harmful material, infringe others’ rights or attempt to bypass access
        controls.
      </p>
      <h2>Your workspace content</h2>
      <p>
        You retain responsibility for your content and for choosing who can
        access it. Workspace owners and project managers control access
        according to the permissions available in the product.
      </p>
      <h2>Service availability</h2>
      <p>
        Features may change as the product develops. Availability and
        uninterrupted operation are not guaranteed. Keep appropriate copies of
        information that is important to your team.
      </p>
      <h2>Public contact form</h2>
      <p>
        Use the contact form for legitimate enquiries. Automated abuse and spam
        are restricted. Messages submitted through the form are private and
        subject to the 180-day retention policy described in our Privacy policy.
      </p>
      <h2>Questions</h2>
      <p>
        Contact us through the Contact page if you have questions about these
        terms or the service.
      </p>
    </article>
  );
}
