const STORAGE_KEY = "teamboard:invitation-return";
const MAX_AGE_MS = 30 * 60 * 1000;

type StoredInvitationReturn = {
  path: string;
  expiresAt: number;
};

export function getSafeInvitationReturn(
  value: string | null,
): string | null {
  if (!value) return null;

  try {
    const url = new URL(value, "https://teamboard.local");

    if (url.origin !== "https://teamboard.local") {
      return null;
    }

    if (url.pathname !== "/accept-invitation/") {
      return null;
    }

    const token = url.searchParams.get("token");

    if (!token || token.length > 200) {
      return null;
    }

    return `/accept-invitation/?${new URLSearchParams({
      token,
    }).toString()}`;
  } catch {
    return null;
  }
}

export function saveInvitationReturn(
  value: string | null,
): void {
  const path = getSafeInvitationReturn(value);

  if (!path || typeof window === "undefined") return;

  const stored: StoredInvitationReturn = {
    path,
    expiresAt: Date.now() + MAX_AGE_MS,
  };

  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(stored),
    );
  } catch {
    // Storage may be unavailable in some browsers.
  }
}

export function readInvitationReturn(): string | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);

    if (!raw) return null;

    const stored = JSON.parse(raw) as StoredInvitationReturn;

    if (
      typeof stored.expiresAt !== "number" ||
      Date.now() >= stored.expiresAt
    ) {
      clearInvitationReturn();
      return null;
    }

    const path = getSafeInvitationReturn(stored.path);

    if (!path) {
      clearInvitationReturn();
    }

    return path;
  } catch {
    clearInvitationReturn();
    return null;
  }
}

export function clearInvitationReturn(): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage may be unavailable in some browsers.
  }
}

export function getInvitationAuthUrl(
  route: "/login" | "/register",
  returnPath: string | null,
): string {
  const safePath = getSafeInvitationReturn(returnPath);

  if (!safePath) return route;

  return `${route}?${new URLSearchParams({
    next: safePath,
  }).toString()}`;
}