const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ApiOptions = RequestInit & {
  token?: string;
};

export type LoginResponse = {
  access: string;
};

export type RegisterResponse = {
  detail: string;
};

export type CurrentUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  date_joined: string;
  is_email_verified: boolean;
};

export type ApiValidationErrors = Record<
  string,
  string[] | string
>;

let refreshPromise: Promise<string> | null = null;

function notifyAuthLogout() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new Event("teamboard:auth-logout"),
    );
  }
}


async function performRefresh(): Promise<string> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}/api/v1/accounts/refresh/`,
      {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  } catch {
    throw new ApiError(
      "Unable to connect to the server. Please try again.",
      0,
    );
  }

  const data = await parseResponse(response);

  if (!response.ok) {
    if (response.status === 401) {
      notifyAuthLogout();
    }

    throw new ApiError(
      getErrorMessage(data),
      response.status,
      getValidationErrors(data),
    );
  }

  const access =
    typeof data === "object" &&
    data !== null &&
    "access" in data &&
    typeof data.access === "string"
      ? data.access
      : null;

  if (!access) {
    throw new ApiError(
      "The server returned an invalid refresh response. Please try again.",
      502,
    );
  }

  return access;
}


function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refresh: Promise<string> =
    typeof navigator !== "undefined" &&
    typeof navigator.locks?.request === "function"
      ? new Promise<string>((resolve, reject) => {
          navigator.locks.request(
            "teamboard:refresh",
            async () => {
              try {
                resolve(await performRefresh());
              } catch (error) {
                reject(error);
              }
            },
          ).catch(reject);
        })
      : performRefresh();

  const sharedRefresh = refresh.finally(() => {
    if (refreshPromise === sharedRefresh) {
      refreshPromise = null;
    }
  });

  refreshPromise = sharedRefresh;
  return sharedRefresh;
}


export class ApiError extends Error {
  status: number;
  errors: ApiValidationErrors | null;

  constructor(
    message: string,
    status: number,
    errors: ApiValidationErrors | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }
}

async function parseResponse(
  response: Response,
): Promise<unknown> {
  const contentType =
    response.headers.get("content-type");

  if (!contentType?.includes("application/json")) {
    return null;
  }

  return response.json().catch(() => null);
}

function getErrorMessage(data: unknown): string {
  if (
    typeof data === "object" &&
    data !== null &&
    "detail" in data &&
    typeof data.detail === "string"
  ) {
    return data.detail;
  }

  if (
    typeof data === "object" &&
    data !== null &&
    "message" in data &&
    typeof data.message === "string"
  ) {
    return data.message;
  }

  return "Something went wrong. Please try again.";
}

function getValidationErrors(
  data: unknown,
): ApiValidationErrors | null {
  if (
    typeof data !== "object" ||
    data === null ||
    Array.isArray(data)
  ) {
    return null;
  }

  const errors: ApiValidationErrors = {};

  for (const [key, value] of Object.entries(data)) {
    if (
      typeof value === "string" ||
      (Array.isArray(value) &&
        value.every(
          (item) => typeof item === "string",
        ))
    ) {
      errors[key] = value;
    }
  }

  return Object.keys(errors).length > 0
    ? errors
    : null;
}

export async function apiFetch<T>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const {
    token,
    headers,
    ...requestOptions
  } = options;

  async function makeRequest(
    requestToken?: string,
  ): Promise<Response> {
    try {
      return await fetch(`${API_URL}${path}`, {
        ...requestOptions,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(requestToken
            ? {
                Authorization: `Bearer ${requestToken}`,
              }
            : {}),
          ...headers,
        },
      });
    } catch {
      throw new ApiError(
        "Unable to connect to the server. Please try again.",
        0,
      );
    }
  }

  let response = await makeRequest(token);

  /*
   * Only authenticated API requests should be retried.
   * The refresh endpoint itself must never recursively
   * try to refresh again.
   */
  const isRefreshRequest =
    path === "/api/v1/accounts/refresh/";

  if (
    response.status === 401 &&
    token &&
    !isRefreshRequest
  ) {
    const newAccessToken = await refreshAccessToken();

    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("teamboard:auth-refreshed", {
          detail: {
            accessToken: newAccessToken,
          },
        }),
      );
    }

    // Retry the original request only once.
    response = await makeRequest(newAccessToken);

    // If the new token is also rejected, end the session.
    if (response.status === 401) {
      notifyAuthLogout();
    }
  }

  const data = await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(data),
      response.status,
      getValidationErrors(data),
    );
  }

  return data as T;
}

export function login(
  email: string,
  password: string,
) {
  return apiFetch<LoginResponse>(
    "/api/v1/accounts/login/",
    {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
      }),
    },
  );
}

export function register(
  email: string,
  password: string,
  passwordConfirm: string,
) {
  return apiFetch<RegisterResponse>(
    "/api/v1/accounts/register/",
    {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        password_confirm: passwordConfirm,
      }),
    },
  );
}


export async function refreshToken(): Promise<LoginResponse> {
  return {
    access: await refreshAccessToken(),
  };
}


export function getCurrentUser(token: string) {
  return apiFetch<CurrentUser>(
    "/api/v1/accounts/me/",
    {
      method: "GET",
      token,
    },
  );
}

export function logout(token: string) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/logout/",
    {
      method: "POST",
      token,
    },
  );
}

export function requestPasswordReset(
  email: string,
) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/password/reset/",
    {
      method: "POST",
      body: JSON.stringify({
        email,
      }),
    },
  );
}

export function confirmPasswordReset(
  uid: string,
  token: string,
  newPassword: string,
  passwordConfirm: string,
) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/password/reset/confirm/",
    {
      method: "POST",
      body: JSON.stringify({
        uid,
        token,
        new_password: newPassword,
        password_confirm: passwordConfirm,
      }),
    },
  );
}

export function verifyEmail(
  uid: string,
  token: string,
) {
  const params = new URLSearchParams({
    uid,
    token,
  });

  return apiFetch<{ detail: string }>(
    `/api/v1/accounts/email/verify/?${params.toString()}`,
    {
      method: "GET",
    },
  );
}

export function resendVerificationEmail(
  email: string,
) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/email/resend/",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
  );
}

export type UserSession = {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  ip_address: string | null;
  user_agent: string;
  is_active: boolean;
  is_current: boolean;
};

export type RevokeOtherSessionsResponse = {
  detail: string;
  revoked_count: number;
};

export function getSessions(token: string) {
  return apiFetch<UserSession[]>(
    "/api/v1/accounts/sessions/",
    {
      method: "GET",
      token,
    },
  );
}

export function revokeSession(
  token: string,
  sessionId: string,
) {
  return apiFetch<{ detail: string }>(
    `/api/v1/accounts/sessions/${encodeURIComponent(sessionId)}/`,
    {
      method: "DELETE",
      token,
    },
  );
}

export function revokeOtherSessions(token: string) {
  return apiFetch<RevokeOtherSessionsResponse>(
    "/api/v1/accounts/sessions/revoke-others/",
    {
      method: "POST",
      token,
    },
  );
}


export type UpdateProfileInput = {
  first_name: string;
  last_name: string;
};

export function updateCurrentUser(
  token: string,
  data: UpdateProfileInput,
) {
  return apiFetch<CurrentUser>("/api/v1/accounts/me/", {
    method: "PATCH",
    token,
    body: JSON.stringify(data),
  });
}

export type ChangePasswordInput = {
  current_password: string;
  new_password: string;
  password_confirm: string;
};

export function changePassword(
  token: string,
  data: ChangePasswordInput,
) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/password/change/",
    {
      method: "POST",
      token,
      body: JSON.stringify(data),
    },
  );
}

export type OrganizationRole =
  | "owner"
  | "admin"
  | "member";

export type Organization = {
  id: number;
  name: string;
  slug: string;
  role: OrganizationRole | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedOrganizations = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Organization[];
};

export function getOrganizations(
  token: string,
  page = 1,
) {
  const params = new URLSearchParams();

  params.set("page", String(page));

  return apiFetch<PaginatedOrganizations>(
    `/api/v1/organizations/?${params.toString()}`,
    {
      method: "GET",
      token,
    },
  );
}
