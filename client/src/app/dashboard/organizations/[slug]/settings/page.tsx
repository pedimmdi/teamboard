"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  updateOrganization,
  deleteOrganization,
  leaveOrganization,
} from "@/lib/api";

import { useAuth } from "@/lib/auth";
import { useOrganizationContext } from "../organization-context";

import ConfirmActionModal from "./confirm-action-modal";
import SettingsTransferModal from "./settings-transfer-modal";

import styles from "./settings.module.css";

export default function SettingsPage() {
  const { accessToken } = useAuth();
  const { organization, updateOrganization: updateContext } =
    useOrganizationContext();

  const [name, setName] = useState(organization.name);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const canEdit =
    organization.role === "owner" ||
    organization.role === "admin";

  const normalizedName = name.trim();
  const hasChanges = normalizedName !== organization.name;

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
      setError("Organization name is required.");
      return;
    }

    if (normalizedName.length > 255) {
      setError("Organization name must be 255 characters or fewer.");
      return;
    }

    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updated = await updateOrganization(
        accessToken,
        organization.slug,
        normalizedName,
      );

      updateContext(updated);
      setName(updated.name);
      setSuccess("Organization settings saved successfully.");
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
        setError("Unable to save organization settings.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCopyId() {
    try {
      await navigator.clipboard.writeText(organization.id);
      setIsCopied(true);
    } catch {
      setError("Unable to copy organization ID.");
    }
  }

  async function handleLeave() {
    if (!accessToken) {
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (organization.role === "owner") {
      throw new Error("Owners must transfer ownership before leaving.");
    }

    await leaveOrganization(accessToken, organization.slug);

    setActiveModal(null);
    router.replace("/dashboard/organizations");
    router.refresh();
  }

  async function handleDelete() {
    if (!accessToken) {
      throw new Error("Your session has expired. Please sign in again.");
    }

    if (organization.role !== "owner") {
      throw new Error("Only the organization owner can delete it.");
    }

    await deleteOrganization(accessToken, organization.slug);

    setActiveModal(null);
    router.replace("/dashboard/organizations");
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
        <p>Manage your organization settings.</p>
      </div>

      <div className={styles.card}>
        <h3>General</h3>

        <form onSubmit={handleSave}>
          <div className={styles.fields}>
            <div className={styles.field}>
              <label htmlFor="organization-name">
                Organization name
              </label>

              <input
                id="organization-name"
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
                  ? "This name is visible to organization members."
                  : "Only owners and admins can change this name."}
              </span>
            </div>

            <div className={styles.field}>
              <label htmlFor="organization-id">
                Organization ID
              </label>

              <div className={styles.idField}>
                <input
                  id="organization-id"
                  type="text"
                  value={organization.id}
                  readOnly
                />

                <button
                  type="button"
                  className={styles.copyButton}
                  onClick={() => void handleCopyId()}
                  aria-label="Copy organization ID"
                  title="Copy organization ID"
                >
                  {isCopied ? "Copied" : "Copy"}
                </button>
              </div>

              <span className={styles.helper}>
                Used to identify this organization.
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

        {organization.role === "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>Transfer ownership</h4>
              <p>
                Transfer ownership of this organization to another member.
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

        {organization.role !== "owner" && (
          <div className={styles.dangerRow}>
            <div>
              <h4>Leave organization</h4>
              <p>
                You will lose access to this organization and its resources.
              </p>
            </div>

            <button
              type="button"
              className={styles.secondaryDangerButton}
              onClick={() => setActiveModal("leave")}
            >
              Leave organization
            </button>
          </div>
        )}

        {organization.role === "owner" && (
          <div className={`${styles.dangerRow} ${styles.deleteRow}`}>
            <div>
              <h4>Delete organization</h4>
              <p>
                Permanently delete this organization and its associated data.
              </p>
            </div>

            <button
              type="button"
              className={styles.deleteButton}
              onClick={() => setActiveModal("delete")}
            >
              Delete organization
            </button>
          </div>
        )}
      </div>

      {activeModal === "transfer" && accessToken && (
        <SettingsTransferModal
          accessToken={accessToken}
          slug={organization.slug}
          onClose={() => setActiveModal(null)}
          onTransferred={handleTransferred}
        />
      )}

      {activeModal === "leave" && (
        <ConfirmActionModal
          title={`Leave ${organization.name}?`}
          description="You will lose access to this organization. You can only rejoin if you are invited again."
          confirmLabel="Leave organization"
          pendingLabel="Leaving..."
          onClose={() => setActiveModal(null)}
          onConfirm={handleLeave}
        />
      )}

      {activeModal === "delete" && (
        <ConfirmActionModal
          title={`Delete ${organization.name}?`}
          description="This action permanently deletes the organization and its associated data. It cannot be undone."
          confirmLabel="Delete organization"
          pendingLabel="Deleting..."
          organizationName={organization.name}
          onClose={() => setActiveModal(null)}
          onConfirm={handleDelete}
        />
      )}
    </section>
  );
}
