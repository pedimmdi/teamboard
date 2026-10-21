const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ApiOptions = RequestInit & {
  token?: string;
};

type TokenResponse = {
  access: string;
  refresh: string;
};

export type LoginResponse = TokenResponse;

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
  const { token, headers, ...requestOptions } = options;

  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...requestOptions,
      headers: {
        "Content-Type": "application/json",
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
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

export function refreshToken(refresh: string) {
  return apiFetch<TokenResponse>(
    "/api/v1/accounts/refresh/",
    {
      method: "POST",
      body: JSON.stringify({
        refresh,
      }),
    },
  );
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

export function logout(
  token: string,
  refresh: string,
) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/logout/",
    {
      method: "POST",
      token,
      body: JSON.stringify({
        refresh,
      }),
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
