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

async function parseResponse(response: Response) {
  return response.json().catch(() => null);
}

export async function apiFetch<T>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const { token, headers, ...requestOptions } = options;

  const response = await fetch(`${API_URL}${path}`, {
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

  const data = await parseResponse(response);

  if (!response.ok) {
    throw new Error(
      data?.detail ??
        "Something went wrong. Please try again.",
    );
  }

  return data as T;
}

export function login(email: string, password: string) {
  return apiFetch<LoginResponse>("/api/v1/accounts/login/", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
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

export function requestPasswordReset(email: string) {
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

export function verifyEmail(uid: string, token: string) {
  const params = new URLSearchParams({ uid, token });

  return apiFetch<{ detail: string }>(
    `/api/v1/accounts/email/verify/?${params.toString()}`,
    { method: "GET" },
  );
}

export function resendVerificationEmail(email: string) {
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/email/resend/",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
  );
}
