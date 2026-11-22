"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import WorkspaceOverview from "../workspace-overview";

import { useTransientMessage } from "@/hooks/use-transient-message";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  updateWorkspace,
  updateResourceAvatar,
  deleteWorkspace,
  leaveWorkspace,
} from "@/lib/api";

import ResourceAvatarEditor from "@/components/ui/ResourceAvatarEditor";
import { useAuth } from "@/lib/auth";
import { useWorkspaceContext } from "../workspace-context";

import ConfirmActionModal from "./confirm-action-modal";
import SettingsTransferModal from "./settings-transfer-modal";

import styles from "./settings.module.css";

export default function SettingsPage() {
  const { ui } = useWorkspaceLocale();
  const { accessToken } = useAuth();
  const { workspace, updateWorkspace: updateContext } =
    useWorkspaceContext();

  const [name, setName] = useState(workspace.name);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useTransientMessage<string | null>(null);
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
        <h2>{ui("Settings")}</h2>
        <p>{ui("Manage your workspace settings.")}</p>
      </div>

      <WorkspaceOverview />

      <div className={styles.card}>
        <h3>{ui("General")}</h3>

        <form onSubmit={handleSave}>
          <div className={styles.fields}>
            <div className={styles.field}>
              <label htmlFor="workspace-name">{ui("Workspace name")}</label>

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
                  ? ui("This name is visible to workspace members.")
                  : ui("Only owners and admins can change this name.")}
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="workspace-id">{ui("Workspace ID")}</label>

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
                  aria-label={ui("Copy workspace ID")}
                  title={ui("Copy workspace ID")}
                >
                  {isCopied ? ui("Copied") : ui("Copy")}
                </button>
              </div>

              <span className={styles.helper}>{ui("Used to identify this workspace.")}</span>
            </div>
          </div>

          {error && (
            <p className={styles.error} role="alert">
              {ui(error)}
            </p>
          )}

          {success && (
            <p className={styles.success} role="status">
              {ui(success)}
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
                {isSaving ? ui("Saving...") : ui("Save changes")}
              </button>
            </div>
          )}
        </form>
      </div>

      {canEdit && accessToken && (
        <ResourceAvatarEditor
          name={workspace.name}
          avatar={workspace.avatar}
          label={ui("Workspace image")}
          onSave={async (image) => {
            const updated = await updateResourceAvatar(accessToken, workspace.slug, image);
            updateContext(updated);
            window.dispatchEvent(new CustomEvent("teamboard:workspace-updated", { detail: updated }));
          }}
        />
      )}
      <div className={styles.dangerZone}>
        <h3>{ui("Danger zone")}</h3>

        {workspace.role === "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>{ui("Transfer ownership")}</h4>
              <p>{ui("Transfer ownership of this workspace to another member.")}</p>
            </div>

            <button
              type="button"
              className={styles.secondaryDangerButton}
              onClick={() => setActiveModal("transfer")}
            >{ui("Transfer ownership")}</button>
          </div>
        )}

        {workspace.role !== "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>{ui("Leave workspace")}</h4>
              <p>{ui("You will lose access to this workspace and its resources.")}</p>
            </div>

            <button
              type="button"
              className={styles.secondaryDangerButton}
              onClick={() => setActiveModal("leave")}
            >{ui("Leave workspace")}</button>
          </div>
        )}

        {workspace.role === "owner" && (
          <div className={`${styles.dangerRow} ${styles.deleteRow}`}>
            <div>
              <h4>{ui("Delete workspace")}</h4>
              <p>{ui("Permanently delete this workspace and its associated data.")}</p>
            </div>

            <button
              type="button"
              className={styles.deleteButton}
              onClick={() => setActiveModal("delete")}
            >{ui("Delete workspace")}</button>
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
          title={ui("Leave {0}?", workspace.name)}
          description={ui("You will lose access to this workspace. You can only rejoin if you are invited again.")}
          confirmLabel={ui("Leave workspace")}
          pendingLabel="Leaving..."
          onClose={() => setActiveModal(null)}
          onConfirm={handleLeave}
        />
      )}

      {activeModal === "delete" && (
        <ConfirmActionModal
          title={ui("Delete {0}?", workspace.name)}
          description={ui("This action permanently deletes the workspace and its associated data. It cannot be undone.")}
          confirmLabel={ui("Delete workspace")}
          pendingLabel="Deleting..."
          workspaceName={workspace.name}
          onClose={() => setActiveModal(null)}
          onConfirm={handleDelete}
        />
      )}
    </section>
  );
}
