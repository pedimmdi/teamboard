import { publicMetadata } from "@/lib/website";
import styles from "../website.module.css";
export const metadata = publicMetadata(
  "Privacy — TeamBoard",
  "How TeamBoard handles account information, workspace content and contact messages.",
  "/privacy",
);
export default function Privacy() {
  return (
    <article className={styles.document}>
      <h1>Privacy policy</h1>
      <h2>Information you provide</h2>
      <p>
        TeamBoard processes account details and the projects, tasks, messages
        and files you provide to operate the service. Workspace and project
        access is controlled through memberships and roles.
      </p>
      <h2>Contact messages: 180-day retention</h2>
      <p>
        When you contact us, we receive your name, email address, subject and
        message. These submissions are private, used to respond to enquiries and
        maintain the service, and scheduled for deletion after 180 days.
        Deletion runs periodically, rather than at an exact time of day.
      </p>
      <h2>Authentication and browser storage</h2>
      <p>
        We use an HttpOnly refresh cookie to maintain your sign-in and browser
        storage to remember preferences such as the selected workspace. Keep
        your account credentials private and sign out on shared devices.
      </p>
      <h2>Security and your choices</h2>
      <p>
        You can manage your profile and active sessions within your account. Use
        the Contact page for privacy questions or requests concerning your
        personal information. Avoid sending sensitive information through the
        public contact form.
      </p>
    </article>
  );
}
