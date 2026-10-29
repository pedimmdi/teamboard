
"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import MemberActions from "./member-actions";
import ChangeRoleModal from "./change-role-modal";
import TransferOwnershipModal from "./transfer-ownership-modal";
import RemoveMemberModal from "./remove-member-modal";

import {
  ApiError,
  getWorkspaceMembers,
  type WorkspaceMember,
} from "@/lib/api";
import { useWorkspace } from "../workspace-context";
import styles from "./members.module.css";

export default function MembersPage() {
  const { accessToken } = useAuth();
  const workspace = useWorkspace();

  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [editingMember, setEditingMember] =
    useState<WorkspaceMember | null>(null);
  const [transferringMember, setTransferringMember] =
    useState<WorkspaceMember | null>(null);
  const [removingMember, setRemovingMember] =
    useState<WorkspaceMember | null>(null);

  useEffect(() => {
    if (!accessToken) return;

    const token = accessToken;
    let cancelled = false;

    async function loadMembers() {
      setIsLoading(true);
      setError(null);

      try {
        const data = await getWorkspaceMembers(
          token,
          workspace.slug,
          page,
        );

        if (cancelled) return;

        if (page > 1 && data.results.length === 0) {
          setPage(page - 1);
          return;
        }

        setMembers(data.results);
        setCount(data.count);
        setHasNext(Boolean(data.next));
        setHasPrevious(Boolean(data.previous));
      } catch (err) {
        if (cancelled) return;

        setError(
          err instanceof ApiError
            ? err.message
            : "Unable to load members.",
        );
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadMembers();

    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, page, reloadKey]);

  return (
    <section className={styles.section}>
      <div className={styles.heading}>
        <div>
          <h2>Members</h2>
          <p>People who belong to this workspace.</p>
        </div>
        <span className={styles.count}>{count} members</span>
      </div>

      {isLoading ? (
        <div className={styles.status}>Loading members...</div>
      ) : error ? (
        <div className={styles.status} role="alert">
          <p>{error}</p>
          <button
            type="button"
            onClick={() => setReloadKey((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      ) : members.length === 0 ? (
        <div className={styles.status}>No members found.</div>
      ) : (
        <div className={styles.card}>
          <div className={styles.desktopTable}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th>Joined</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>
                      <div className={styles.memberCell}>
                        <span className={styles.avatar}>
                          {member.user_email.charAt(0).toUpperCase()}
                        </span>
                        <span className={styles.email}>
                          {member.user_email}
                          {member.is_current_user && (
                            <span className={styles.you}> (You)</span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={styles.role}>
                        {member.role}
                      </span>
                    </td>
                    <td>
                      {new Intl.DateTimeFormat("en-US", {
                        month: "short",
                        day: "2-digit",
                        year: "numeric",
                      }).format(new Date(member.joined_at))}
                    </td>
                    <td>
                      <MemberActions
                        member={member}
                        currentRole={workspace.role}
                        onChangeRole={() => setEditingMember(member)}
                        onTransferOwnership={() => setTransferringMember(member)}
                        onRemoveMember={() => setRemovingMember(member)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.mobileList}>
            {members.map((member) => (
              <div key={member.id} className={styles.mobileMember}>
                <div className={styles.mobileMemberTop}>
                  <div className={styles.memberCell}>
                    <span className={styles.avatar}>
                      {member.user_email.charAt(0).toUpperCase()}
                    </span>

                    <div className={styles.mobileMemberInfo}>
                      <span className={styles.email}>
                        {member.user_email}
                        {member.is_current_user && (
                          <span className={styles.you}> (You)</span>
                        )}
                      </span>

                      <span className={styles.mobileJoined}>
                        Joined{" "}
                        {new Intl.DateTimeFormat("en-US", {
                          month: "short",
                          day: "2-digit",
                          year: "numeric",
                        }).format(new Date(member.joined_at))}
                      </span>
                    </div>
                  </div>

                  <MemberActions
                    member={member}
                    currentRole={workspace.role}
                    onChangeRole={() => setEditingMember(member)}
                    onTransferOwnership={() => setTransferringMember(member)}
                    onRemoveMember={() => setRemovingMember(member)}
                  />
                </div>

                <div className={styles.mobileMemberBottom}>
                  <span className={styles.role}>{member.role}</span>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.footer}>
            <span>{count} members total</span>
            <div className={styles.actions}>
              <button
                type="button"
                disabled={!hasPrevious}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                disabled={!hasNext}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {editingMember && accessToken && (
        <ChangeRoleModal
          accessToken={accessToken}
          slug={workspace.slug}
          member={editingMember}
          onClose={() => setEditingMember(null)}
          onUpdated={() => {
            setEditingMember(null);
            setReloadKey((value) => value + 1);
          }}
        />
      )}
      {transferringMember && accessToken && (
        <TransferOwnershipModal
          accessToken={accessToken}
          slug={workspace.slug}
          member={transferringMember}
          onClose={() => setTransferringMember(null)}
          onTransferred={() => {
            setTransferringMember(null);
            setReloadKey((value) => value + 1);
            window.location.reload();
          }}
        />
      )}
      {removingMember && accessToken && (
        <RemoveMemberModal
          accessToken={accessToken}
          slug={workspace.slug}
          member={removingMember}
          onClose={() => setRemovingMember(null)}
          onRemoved={() => {
            setRemovingMember(null);
            setReloadKey((value) => value + 1);
          }}
        />
      )}
    </section>
  );
}
