"use client";

import { FormEvent, useMemo, useState } from "react";

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
      });

      updateUser(updatedUser);

      setFirstName(updatedUser.first_name);
      setLastName(updatedUser.last_name);
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
    firstName.trim() !== user.first_name ||
    lastName.trim() !== user.last_name;

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      <div className={styles.identity}>
        <div className={styles.largeAvatar}>{initials}</div>

        <div className={styles.identityText}>
          <h2>
            {firstName || user.first_name} {lastName || user.last_name}
          </h2>
          <p>{user.email}</p>
        </div>
      </div>

      <div className={styles.divider} />

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