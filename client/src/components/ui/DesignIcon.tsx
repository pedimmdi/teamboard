import styles from "./design-icon.module.css";

export default function DesignIcon({
  name,
}: {
  name: "folder" | "users" | "settings" | "chevron-right" | "chevrons-up-down";
}) {
  return (
    <span
      className={styles.icon}
      style={{ maskImage: `url('/icons/${name}.svg')` }}
      aria-hidden="true"
    />
  );
}
