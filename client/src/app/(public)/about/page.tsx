import Link from "next/link";
import { publicMetadata } from "@/lib/website";
import styles from "../website.module.css";
export const metadata = publicMetadata(
  "About TeamBoard",
  "Learn how TeamBoard brings projects, tasks and conversations into one shared workspace.",
  "/about",
);
export default function About() {
  return (
    <article className={styles.document}>
      <p className={styles.eyebrow}>ABOUT TEAMBOARD</p>
      <h1>Good teamwork starts with clarity.</h1>
      <p>
        TeamBoard helps teams organize their work without losing the
        conversations and context behind it.
      </p>
      <h2>A shared place to move forward</h2>
      <p>
        Our goal is simple: make it easier to see what matters, who owns the
        next step and how work is progressing.
      </p>
      <h2>Designed around real teamwork</h2>
      <p>
        Workspaces and project roles keep collaboration organized. Task boards,
        calendars and private reminders keep priorities visible. Comments,
        mentions and chat bring discussions closer to the work.
      </p>
      <h2>From daily focus to the bigger picture</h2>
      <p>
        Your dashboard highlights tasks and follow-ups. Project reports help
        teams understand progress and workloads when they need a wider view.
      </p>
      <Link className={styles.primary} href="/register">
        Start your workspace →
      </Link>
    </article>
  );
}
