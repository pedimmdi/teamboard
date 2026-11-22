
"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useEffect, useRef, useState } from "react";

import type {
  WorkspaceMember,
  WorkspaceRole,
} from "@/lib/api";

import styles from "./member-actions.module.css";

type Props = {
  member: WorkspaceMember;
  currentRole: WorkspaceRole | null;
  onChangeRole: () => void;
  onTransferOwnership: () => void;
  onRemoveMember: () => void;
};

export default function MemberActions({
  member,
  currentRole,
  onChangeRole,
  onTransferOwnership,
  onRemoveMember,
}: Props) {
  const { ui } = useWorkspaceLocale();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const isOwner = currentRole === "owner";
  const canRemove =
    !member.is_current_user &&
    (isOwner ||
      (currentRole === "admin" && member.role === "member")) &&
    member.role !== "owner";

  const canManageRole =
    isOwner &&
    !member.is_current_user &&
    member.role !== "owner";

  const hasActions = canRemove || canManageRole;

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
        aria-label={ui("Actions for {0}", member.user_email)}
        aria-expanded={isOpen}
        aria-haspopup="true"
        onClick={() => setIsOpen((value) => !value)}
      >
        ⋯
      </button>

      {isOpen && (
        <div className={styles.menu}>
          {canManageRole && (
            <>
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  onChangeRole();
                }}
              >{ui("Change member role")}</button>

              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  onTransferOwnership();
                }}
              >{ui("Transfer ownership")}</button>
            </>
          )}

          {canRemove && (
            <button
              type="button"
              className={styles.danger}
              onClick={() => {
                setIsOpen(false);
                onRemoveMember();
              }}
            >{ui("Remove from workspace")}</button>
          )}
        </div>
      )}
    </div>
  );
}
