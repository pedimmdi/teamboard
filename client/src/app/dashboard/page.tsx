"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Avatar from "@/components/ui/Avatar";

import { updateCurrentUser } from "@/lib/api";
import { CurrentUser } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import styles from "./dashboard.module.css";

function getInitials(firstName: string, lastName: string) {
  const first = firstName.trim().charAt(0);
  const last = lastName.trim().charAt(0);

  return `${first}${last}`.toUpperCase() || "U";
}

function ProfileForm({
  user,
  accessToken,
}: {
  user: CurrentUser;
  accessToken: string;
}) {
  const [firstName, setFirstName] = useState(user.first_name);
  const [lastName, setLastName] = useState(user.last_name);
  const [avatar, setAvatar] = useState<File | null | undefined>();
  const [preview, setPreview] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const { updateUser } = useAuth();

  const initials = useMemo(
    () => getInitials(firstName, lastName),
    [firstName, lastName],
  );

  const handleCancel = () => {
    setFirstName(user.first_name);
    setLastName(user.last_name);
    setAvatar(undefined);
    setPreview(null);
    if (fileInput.current) fileInput.current.value = "";
    setSuccessMessage("");
    setErrorMessage("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSuccessMessage("");
    setErrorMessage("");

    const normalizedFirstName = firstName.trim();
    const normalizedLastName = lastName.trim();

    if (!normalizedFirstName || !normalizedLastName) {
      setErrorMessage("First name and last name are required.");
      return;
    }

    setIsSaving(true);

    try {
      const updatedUser = await updateCurrentUser(accessToken, {
        first_name: normalizedFirstName,
        last_name: normalizedLastName,
        ...(avatar !== undefined ? { avatar } : {}),
      });

      updateUser(updatedUser);

      setFirstName(updatedUser.first_name);
      setLastName(updatedUser.last_name);
      setAvatar(undefined);
      setPreview(null);
      if (fileInput.current) fileInput.current.value = "";
      setSuccessMessage("Your profile has been updated.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to update your profile.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges =
    avatar !== undefined ||
    firstName.trim() !== user.first_name ||
    lastName.trim() !== user.last_name;

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      <div className={styles.identity}>
        <Avatar
          className={styles.largeAvatar}
          src={avatar === null ? null : preview ?? user.avatar}
          fallback={initials}
          size={64}
        />

        <div className={styles.identityText}>
          <h2>
            {firstName || user.first_name} {lastName || user.last_name}
          </h2>
          <p>{user.email}</p>
        </div>
      </div>

      <div className={styles.divider} />

      <div className={styles.field}>
        <span id="profile-picture-label">Profile picture</span>
        <div
          className={styles.pictureControls}
          role="group"
          aria-labelledby="profile-picture-label"
          aria-describedby="profile-picture-help"
        >
          <input
            ref={fileInput}
            type="file"
            hidden
            aria-label="Choose profile picture"
            accept="image/jpeg,image/png,image/webp"
            disabled={isSaving}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (
                !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
                file.size > 5 * 1024 * 1024
              ) {
                setErrorMessage("Choose a JPEG, PNG, or WebP image up to 5 MB.");
                event.target.value = "";
                return;
              }
              setErrorMessage("");
              setSuccessMessage("");
              setAvatar(file);
              setPreview(URL.createObjectURL(file));
            }}
          />
          <button
            type="button"
            className={styles.uploadPicture}
            disabled={isSaving}
            onClick={() => fileInput.current?.click()}
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M10 13V3M6.5 6.5L10 3L13.5 6.5M4 12V15.5C4 16.33 4.67 17 5.5 17H14.5C15.33 17 16 16.33 16 15.5V12"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {avatar || (user.avatar && avatar !== null) ? "Change photo" : "Upload photo"}
          </button>
          <span className={styles.pictureFileName} title={avatar?.name}>
            {avatar?.name ?? (user.avatar && avatar !== null ? "Current picture" : "No picture")}
          </span>
          {(avatar || user.avatar) && avatar !== null && (
            <button
              type="button"
              className={styles.removePicture}
              disabled={isSaving}
              aria-label="Remove profile picture"
              title="Remove picture"
              onClick={() => {
                setAvatar(user.avatar ? null : undefined);
                setPreview(null);
                if (fileInput.current) fileInput.current.value = "";
              }}
            >
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M3.5 5.5H16.5M8 3H12M5 5.5L5.75 16.25C5.8 16.95 6.38 17.5 7.08 17.5H12.92C13.62 17.5 14.2 16.95 14.25 16.25L15 5.5M8 8.5V14M12 8.5V14"
                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
        </div>
        <small id="profile-picture-help" className={styles.fieldHelp}>
          JPEG, PNG or WebP · Up to 5 MB · Max 4096 × 4096
        </small>
      </div>

      <div className={styles.fieldRow}>
        <label className={styles.field}>
          <span>First name</span>
          <input
            type="text"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            autoComplete="given-name"
            maxLength={150}
          />
        </label>

        <label className={styles.field}>
          <span>Last name</span>
          <input
            type="text"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            autoComplete="family-name"
            maxLength={150}
          />
        </label>
      </div>

      <div className={styles.field}>
        <span>Email address</span>

        <div className={styles.readonlyField}>
          <span>{user.email}</span>

          {user.is_email_verified && (
            <span className={styles.successBadge}>Verified</span>
          )}
        </div>
      </div>

      {successMessage && (
        <p className={styles.successMessage}>{successMessage}</p>
      )}

      {errorMessage && (
        <p className={styles.errorMessage}>{errorMessage}</p>
      )}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.secondaryButton}
          onClick={handleCancel}
          disabled={isSaving || !hasChanges}
        >
          Cancel
        </button>

        <button
          type="submit"
          className={styles.primaryButton}
          disabled={isSaving || !hasChanges}
        >
          {isSaving ? "Saving..." : "Save changes"}
        </button>
      </div>
    </form>
  );
}

export default function DashboardPage() {
  const { user, accessToken, isAuthenticated, isLoading } = useAuth();

  if (isLoading || !isAuthenticated || !user || !accessToken) {
    return null;
  }

  return (
    <section className={styles.page}>
      <div className={styles.content}>
        <header className={styles.pageHeader}>
          <div>
            <h1>Profile</h1>
            <p>Manage your personal information.</p>
          </div>
        </header>

        <ProfileForm user={user} accessToken={accessToken} />
      </div>
    </section>
  );
}
