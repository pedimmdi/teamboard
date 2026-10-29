"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  updateWorkspace,
  deleteWorkspace,
  leaveWorkspace,
} from "@/lib/api";

import { useAuth } from "@/lib/auth";
import { useWorkspaceContext } from "../workspace-context";

import ConfirmActionModal from "./confirm-action-modal";
import SettingsTransferModal from "./settings-transfer-modal";

import styles from "./settings.module.css";

export default function SettingsPage() {
  const { accessToken } = useAuth();
  const { workspace, updateWorkspace: updateContext } =
    useWorkspaceContext();

  const [name, setName] = useState(workspace.name);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const canEdit =
    workspace.role === "owner" ||
    workspace.role === "admin";

  const normalizedName = name.trim();
  const hasChanges = normalizedName !== workspace.name;

  const router = useRouter();

  const [activeModal, setActiveModal] = useState<
    "transfer" | "leave" | "delete" | null
  >(null);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!accessToken || !canEdit || isSaving || !hasChanges) {
      return;
    }

    if (!normalizedName) {
      setError("Workspace name is required.");
      return;
    }

    if (normalizedName.length > 255) {
      setError("Workspace name must be 255 characters or fewer.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updated = await updateWorkspace(
        accessToken,
        workspace.slug,
        normalizedName,
      );

      updateContext(updated);
      setName(updated.name);
      setSuccess("Workspace settings saved successfully.");
    } catch (err) {
      if (err instanceof ApiError) {
        const nameErrors = err.errors?.name;

        if (Array.isArray(nameErrors)) {
          setError(nameErrors.join(" "));
        } else if (typeof nameErrors === "string") {
          setError(nameErrors);
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to save workspace settings.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCopyId() {
    try {
      await navigator.clipboard.writeText(workspace.id);
      setIsCopied(true);
    } catch {
      setError("Unable to copy workspace ID.");
    }
  }

  async function handleLeave() {
    if (!accessToken) {
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (workspace.role === "owner") {
      throw new Error("Owners must transfer ownership before leaving.");
    }

    await leaveWorkspace(accessToken, workspace.slug);

    setActiveModal(null);
    router.replace("/dashboard/workspaces");
    router.refresh();
  }

  async function handleDelete() {
    if (!accessToken) {
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (workspace.role !== "owner") {
      throw new Error("Only the workspace owner can delete it.");
    }

    await deleteWorkspace(accessToken, workspace.slug);

    setActiveModal(null);
    router.replace("/dashboard/workspaces");
    router.refresh();
  }

  function handleTransferred() {
    setActiveModal(null);
    window.location.reload();
  }

  return (
    <section className={styles.page}>
      <div className={styles.heading}>
        <h2>Settings</h2>
        <p>Manage your workspace settings.</p>
      </div>

      <div className={styles.card}>
        <h3>General</h3>

        <form onSubmit={handleSave}>
          <div className={styles.fields}>
            <div className={styles.field}>
              <label htmlFor="workspace-name">
                Workspace name
              </label>

              <input
                id="workspace-name"
                type="text"
                value={name}
                maxLength={255}
                disabled={!canEdit || isSaving}
                aria-invalid={Boolean(error)}
                onChange={(event) => {
                  setName(event.target.value);
                  setError(null);
                  setSuccess(null);
                }}
              />

              <span className={styles.helper}>
                {canEdit
                  ? "This name is visible to workspace members."
                  : "Only owners and admins can change this name."}
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="workspace-id">
                Workspace ID
              </label>

              <div className={styles.idField}>
                <input
                  id="workspace-id"
                  type="text"
                  value={workspace.id}
                  readOnly
                />

                <button
                  type="button"
                  className={styles.copyButton}
                  onClick={() => void handleCopyId()}
                  aria-label="Copy workspace ID"
                  title="Copy workspace ID"
                >
                  {isCopied ? "Copied" : "Copy"}
                </button>
              </div>

              <span className={styles.helper}>
                Used to identify this workspace.
              </span>
            </div>
          </div>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          {success && (
            <p className={styles.success} role="status">
              {success}
            </p>
          )}

          {canEdit && (
            <div className={styles.formActions}>
              <button
                type="submit"
                className={styles.saveButton}
                disabled={
                  isSaving ||
                  !hasChanges ||
                  !normalizedName ||
                  normalizedName.length > 255
                }
              >
                {isSaving ? "Saving..." : "Save changes"}
              </button>
            </div>
          )}
        </form>
      </div>

      <div className={styles.dangerZone}>
        <h3>Danger zone</h3>

        {workspace.role === "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>Transfer ownership</h4>
              <p>
                Transfer ownership of this workspace to another member.
              </p>
            </div>

            <button
              type="button"
              className={styles.secondaryDangerButton}
              onClick={() => setActiveModal("transfer")}
            >
              Transfer ownership
            </button>
          </div>
        )}

        {workspace.role !== "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>Leave workspace</h4>
              <p>
                You will lose access to this workspace and its resources.
              </p>
            </div>

            <button
              type="button"
              className={styles.secondaryDangerButton}
              onClick={() => setActiveModal("leave")}
            >
              Leave workspace
            </button>
          </div>
        )}

        {workspace.role === "owner" && (
          <div className={`${styles.dangerRow} ${styles.deleteRow}`}>
            <div>
              <h4>Delete workspace</h4>
              <p>
                Permanently delete this workspace and its associated data.
              </p>
            </div>

            <button
              type="button"
              className={styles.deleteButton}
              onClick={() => setActiveModal("delete")}
            >
              Delete workspace
            </button>
          </div>
        )}
      </div>

      {activeModal === "transfer" && accessToken && (
        <SettingsTransferModal
          accessToken={accessToken}
          slug={workspace.slug}
          onClose={() => setActiveModal(null)}
          onTransferred={handleTransferred}
        />
      )}

      {activeModal === "leave" && (
        <ConfirmActionModal
          title={`Leave ${workspace.name}?`}
          description="You will lose access to this workspace. You can only rejoin if you are invited again."
          confirmLabel="Leave workspace"
          pendingLabel="Leaving..."
          onClose={() => setActiveModal(null)}
          onConfirm={handleLeave}
        />
      )}

      {activeModal === "delete" && (
        <ConfirmActionModal
          title={`Delete ${workspace.name}?`}
          description="This action permanently deletes the workspace and its associated data. It cannot be undone."
          confirmLabel="Delete workspace"
          pendingLabel="Deleting..."
          workspaceName={workspace.name}
          onClose={() => setActiveModal(null)}
          onConfirm={handleDelete}
        />
      )}
    </section>
  );
}
