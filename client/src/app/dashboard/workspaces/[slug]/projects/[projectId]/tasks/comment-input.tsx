import { useRef, useState, type TextareaHTMLAttributes } from "react";
import type { ProjectMember } from "@/lib/api";
import styles from "./task-comments.module.css";

export default function CommentInput({
  value,
  onValueChange,
  members,
  ...props
}: Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange"> & {
  value: string;
  onValueChange: (value: string) => void;
  members: ProjectMember[];
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const [caret, setCaret] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const match = !dismissed && value.slice(0, caret).match(/(?:^|\s)@([^\s]*)$/);
  const suggestions = match && !props.disabled
    ? members.filter((member) => member.user_email.toLowerCase().includes(match[1].toLowerCase())).slice(0, 5)
    : [];

  return (
    <div className={styles.commentInput}>
      <textarea
        {...props}
        ref={input}
        value={value}
        onChange={(event) => {
          setCaret(event.target.selectionStart);
          setDismissed(false);
          onValueChange(event.target.value);
        }}
        onSelect={(event) => setCaret(event.currentTarget.selectionStart)}
        onKeyDown={(event) => {
          if (event.key === "Escape" && suggestions.length) {
            event.preventDefault();
            setDismissed(true);
          }
        }}
      />
      {match && suggestions.length > 0 && (
        <div className={styles.mentions} role="group" aria-label="Mention a project member">
          {suggestions.map((member) => (
            <button key={member.id} type="button" onClick={() => {
              const start = caret - match[1].length - 1;
              const end = caret + (value.slice(caret).match(/^\S*/)?.[0].length ?? 0);
              const mention = `@${member.user_email} `;
              onValueChange(value.slice(0, start) + mention + value.slice(end));
              setDismissed(true);
              requestAnimationFrame(() => {
                input.current?.focus();
                input.current?.setSelectionRange(start + mention.length, start + mention.length);
              });
            }}>
              {member.user_email}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
