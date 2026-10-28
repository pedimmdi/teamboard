
"use client";

import { useEffect, useRef, useState } from "react";

import type { OrganizationInvitation } from "@/lib/api";

import styles from "./invitation-actions.module.css";

type Props = {
  invitation: OrganizationInvitation;
  onResend: () => void;
  onRevoke: () => void;
};

export default function InvitationActions({
  invitation,
  onResend,
  onRevoke,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const canResend =
    invitation.status === "pending" ||
    invitation.status === "expired";

  const canRevoke = invitation.status === "pending";
  const hasActions = canResend || canRevoke;

  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  if (!hasActions) return null;

  return (
    <div ref={containerRef} className={styles.container}>
      <button
        type="button"
        className={styles.trigger}
        aria-label={`Actions for ${invitation.email}`}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        onClick={() => setIsOpen((value) => !value)}
      >
        ⋯
      </button>

      {isOpen && (
        <div className={styles.menu} role="menu">
          {canResend && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setIsOpen(false);
                onResend();
              }}
            >
              Resend invitation
            </button>
          )}

          {canRevoke && (
            <button
              type="button"
              role="menuitem"
              className={styles.danger}
              onClick={() => {
                setIsOpen(false);
                onRevoke();
              }}
            >
              Revoke invitation
            </button>
          )}
        </div>
      )}
    </div>
  );
}
