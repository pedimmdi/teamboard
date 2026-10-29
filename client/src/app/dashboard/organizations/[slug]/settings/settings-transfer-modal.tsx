
"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  getOrganizationMembers,
  transferOrganizationOwnership,
  type OrganizationMember,
} from "@/lib/api";

import styles from "./settings-transfer-modal.module.css";

type Props = {
  accessToken: string;
  slug: string;
  onClose: () => void;
  onTransferred: () => void;
};

export default function SettingsTransferModal({
  accessToken,
  slug,
  onClose,
  onTransferred,
}: Props) {
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  const submittingRef = useRef(false);

  useEffect(() => {
    closeRef.current = onClose;
    submittingRef.current = isSubmitting;
  }, [onClose, isSubmitting]);

  useEffect(() => {
    let cancelled = false;

    async function loadMembers() {
      setIsLoading(true);

      try {
        const allMembers: OrganizationMember[] = [];
        let page = 1;
        let hasNext = true;

        while (hasNext) {
          const data = await getOrganizationMembers(
            accessToken,
            slug,
            page,
          );

          if (cancelled) return;

          allMembers.push(...data.results);
          hasNext = Boolean(data.next);
          page += 1;
        }

        setMembers(
          allMembers.filter(
            (member) =>
              !member.is_current_user &&
              member.role !== "owner",
          ),
        );
      } catch (err) {
        if (!cancelled) {
          setMembers([]);
          setSelectedId("");
          setError(
            err instanceof ApiError
              ? err.message
              : "Unable to load organization members.",
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadMembers();

    return () => {
      cancelled = true;
    };
  }, [accessToken, slug]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement as HTMLElement | null;

    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submittingRef.current) {
        closeRef.current();
        return;
      }

      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), select:not(:disabled)',
      );

      if (!focusable?.length) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, []);

  async function handleTransfer() {
    if (isSubmitting || !selectedId || !confirmed) return;

    setIsSubmitting(true);
    submittingRef.current = true;
    setError(null);

    try {
      await transferOrganizationOwnership(
        accessToken,
        slug,
        selectedId,
      );

      onTransferred();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to transfer ownership.",
      );
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  const selectedMember = members.find(
    (member) => member.id === selectedId,
  );

  return (
    <div className={styles.overlay}>
      <div
        ref={dialogRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-transfer-title"
        tabIndex={-1}
      >
        <h2 id="settings-transfer-title">
          Transfer ownership
        </h2>

        <p className={styles.description}>
          Select a member to become the new organization owner.
        </p>

        {isLoading ? (
          <p className={styles.status}>Loading members...</p>
        ) : members.length === 0 ? (
          <p className={styles.status}>
            No eligible members are available.
          </p>
        ) : (
          <>
            <label htmlFor="transfer-member">
              New owner
            </label>

            <select
              id="transfer-member"
              value={selectedId}
              disabled={isSubmitting}
              onChange={(event) => setSelectedId(event.target.value)}
            >
              <option value="">Select a member</option>

              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.user_email}
                </option>
              ))}
            </select>

            {selectedMember && (
              <div className={styles.warning}>
                {selectedMember.user_email} will become the owner.
                Your role will change to Admin.
              </div>
            )}

            <label className={styles.confirmation}>
              <input
                type="checkbox"
                checked={confirmed}
                disabled={isSubmitting}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              <span>
                I understand that I will lose owner-only permissions.
              </span>
            </label>
          </>
        )}

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.cancelButton}
            disabled={isSubmitting}
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            type="button"
            className={styles.transferButton}
            disabled={!selectedId || !confirmed || isSubmitting || isLoading}
            onClick={() => void handleTransfer()}
          >
            {isSubmitting ? "Transferring..." : "Transfer ownership"}
          </button>
        </div>
      </div>
    </div>
  );
}
