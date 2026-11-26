const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const INITIAL_READ_TIMEOUT = 10_000;

type ApiOptions = RequestInit & {
  token?: string;
  responseType?: "blob";
  timeoutMs?: number;
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
  avatar: string | null;
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


function connectionError() {
  return new ApiError("Unable to connect to the server. Please try again.", 0);
}

async function performRefresh(signal: AbortSignal): Promise<string> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}/api/v1/accounts/refresh/`,
      {
        method: "POST",
        signal,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  } catch {
    throw connectionError();
  }

  const data = await parseResponse(response);
  if (signal.aborted) throw connectionError();

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

  const signal = AbortSignal.timeout(INITIAL_READ_TIMEOUT);
  const refresh =
    typeof navigator !== "undefined" &&
    typeof navigator.locks?.request === "function"
      ? Promise.resolve(navigator.locks.request("teamboard:refresh", { signal }, () => performRefresh(signal)))
      : performRefresh(signal);

  const sharedRefresh = refresh.catch((error: unknown) => {
    if (signal.aborted) throw connectionError();
    throw error;
  }).finally(() => {
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
    responseType,
    timeoutMs,
    ...requestOptions
  } = options;
  const deadline = timeoutMs && typeof AbortSignal !== "undefined" ? AbortSignal.timeout(timeoutMs) : undefined;
  const signal = deadline && requestOptions.signal
    ? AbortSignal.any([deadline, requestOptions.signal])
    : deadline ?? requestOptions.signal;

  async function makeRequest(
    requestToken?: string,
  ): Promise<Response> {
    try {
      return await fetch(`${API_URL}${path}`, {
        ...requestOptions,
        signal,
        credentials: "include",
        headers: {
          ...(requestOptions.body instanceof FormData
            ? {}
            : { "Content-Type": "application/json" }),
          ...(requestToken
            ? {
                Authorization: `Bearer ${requestToken}`,
              }
            : {}),
          ...headers,
        },
      });
    } catch {
      throw connectionError();
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

  if (response.ok && responseType === "blob") return (await response.blob()) as T;

  const data = await parseResponse(response);
  if (deadline?.aborted) throw connectionError();

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
      timeoutMs: INITIAL_READ_TIMEOUT,
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
  return apiFetch<{ detail: string }>(
    "/api/v1/accounts/email/verify/",
    {
      method: "POST",
      body: JSON.stringify({ uid, token }),
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

export type PaginatedSessions = {
  count: number;
  next: string | null;
  previous: string | null;
  results: UserSession[];
};

export function getSessions(token: string, page: number) {
  return apiFetch<PaginatedSessions>(
    `/api/v1/accounts/sessions/?page=${page}`,
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
  avatar?: File | null;
};

export function updateCurrentUser(
  token: string,
  data: UpdateProfileInput,
) {
  let body: string | FormData = JSON.stringify(data);
  if (data.avatar instanceof File) {
    body = new FormData();
    body.set("first_name", data.first_name);
    body.set("last_name", data.last_name);
    body.set("avatar", data.avatar);
  }
  return apiFetch<CurrentUser>("/api/v1/accounts/me/", {
    method: "PATCH",
    token,
    body,
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

export type WorkspaceRole =
  | "owner"
  | "admin"
  | "member";

export type Workspace = {
  avatar: string | null;
  id: string;
  name: string;
  slug: string;
  role: WorkspaceRole | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedWorkspaces = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Workspace[];
};

export function getWorkspaces(
  token: string,
  page = 1,
) {
  const params = new URLSearchParams();

  params.set("page", String(page));

  return apiFetch<PaginatedWorkspaces>(
    `/api/v1/workspaces/?${params.toString()}`,
    {
      method: "GET",
      token,
      timeoutMs: INITIAL_READ_TIMEOUT,
    },
  );
}

// Share concurrent identical reads only. Never retain responses or permissions.
const workspaceRequests = new Map<string, Promise<Workspace>>();
export function getWorkspace(
  token: string,
  slug: string,
) {
  const key = JSON.stringify([token, slug]);
  const pending = workspaceRequests.get(key);
  if (pending) return pending;
  const request = apiFetch<Workspace>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/`,
    {
      method: "GET",
      token,
      timeoutMs: INITIAL_READ_TIMEOUT,
    },
  );
  workspaceRequests.set(key, request);
  void request.finally(() => workspaceRequests.delete(key)).catch(() => {});
  return request;
}

export type CreateWorkspaceInput = {
  name: string;
};

export function createWorkspace(
  token: string,
  data: CreateWorkspaceInput,
) {
  return apiFetch<Workspace>(
    "/api/v1/workspaces/",
    {
      method: "POST",
      token,
      body: JSON.stringify(data),
    },
  );
}

export type WorkspaceMember = {
  id: string;
  user_id: number;
  user_email: string;
  avatar: string | null;
  role: WorkspaceRole;
  is_current_user: boolean;
  joined_at: string;
};

export type PaginatedWorkspaceMembers = {
  count: number;
  next: string | null;
  previous: string | null;
  results: WorkspaceMember[];
};

export function getWorkspaceMembers(
  token: string,
  slug: string,
  page = 1,
) {
  const params = new URLSearchParams({
    page: String(page),
  });

  return apiFetch<PaginatedWorkspaceMembers>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/members/?${params}`,
    {
      method: "GET",
      token,
    },
  );
}

export function updateWorkspaceMemberRole(
  token: string,
  slug: string,
  membershipId: string,
  role: "admin" | "member",
) {
  return apiFetch<WorkspaceMember>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/members/${encodeURIComponent(membershipId)}/role/`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ role }),
    },
  );
}

export function transferWorkspaceOwnership(
  token: string,
  slug: string,
  membershipId: string,
) {
  return apiFetch<WorkspaceMember>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/transfer-ownership/`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        membership_id: membershipId,
      }),
    },
  );
}

export function removeWorkspaceMember(
  token: string,
  slug: string,
  membershipId: string,
) {
  return apiFetch<null>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/members/${encodeURIComponent(membershipId)}/`,
    {
      method: "DELETE",
      token,
    },
  );
}


export type WorkspaceInvitationStatus =
  | "pending"
  | "accepted"
  | "revoked"
  | "expired";

export type WorkspaceInvitation = {
  id: string;
  email: string;
  status: WorkspaceInvitationStatus;
  invited_by_email: string | null;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
};

export type PaginatedWorkspaceInvitations = {
  count: number;
  next: string | null;
  previous: string | null;
  results: WorkspaceInvitation[];
};

export function getWorkspaceInvitations(
  token: string,
  slug: string,
  page = 1,
) {
  const params = new URLSearchParams({
    page: String(page),
  });

  return apiFetch<PaginatedWorkspaceInvitations>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/invitations/?${params.toString()}`,
    {
      method: "GET",
      token,
    },
  );
}

export function createWorkspaceInvitation(
  token: string,
  slug: string,
  email: string,
) {
  return apiFetch<WorkspaceInvitation>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/invitations/`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ email }),
    },
  );
}

export function resendWorkspaceInvitation(
  token: string,
  slug: string,
  invitationId: string,
) {
  return apiFetch<WorkspaceInvitation>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/invitations/${encodeURIComponent(invitationId)}/resend/`,
    {
      method: "POST",
      token,
    },
  );
}

export function revokeWorkspaceInvitation(
  token: string,
  slug: string,
  invitationId: string,
) {
  return apiFetch<{ detail: string }>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/invitations/${encodeURIComponent(invitationId)}/`,
    {
      method: "DELETE",
      token,
    },
  );
}

export function updateWorkspace(
  token: string,
  slug: string,
  name: string,
) {
  return apiFetch<Workspace>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ name }),
    },
  );
}

export function leaveWorkspace(
  token: string,
  slug: string,
) {
  return apiFetch<null>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/leave/`,
    {
      method: "POST",
      token,
    },
  );
}

export function deleteWorkspace(
  token: string,
  slug: string,
) {
  return apiFetch<null>(
    `/api/v1/workspaces/${encodeURIComponent(slug)}/`,
    {
      method: "DELETE",
      token,
    },
  );
}

export type AcceptWorkspaceInvitationResponse = {
  detail: string;
  workspace: {
    id: string;
    name: string;
    slug: string;
  };
  role: WorkspaceRole;
};

export function acceptWorkspaceInvitation(
  accessToken: string,
  invitationToken: string,
) {
  return apiFetch<AcceptWorkspaceInvitationResponse>(
    "/api/v1/workspaces/invitations/accept/",
    {
      method: "POST",
      token: accessToken,
      body: JSON.stringify({
        token: invitationToken,
      }),
    },
  );
}

export type ProjectRole = "manager" | "member";
export type Project = {
  avatar: string | null;
  id: string;
  name: string;
  description: string;
  role: ProjectRole | null;
  created_at: string;
  updated_at: string;
};
export type ProjectMember = {
  id: string;
  user_id: number;
  user_email: string;
  avatar?: string | null;
  role: ProjectRole;
  is_current_user: boolean;
  joined_at: string;
};
export type PaginatedProjects = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Project[];
};
export type PaginatedProjectMembers = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ProjectMember[];
};
export type ProjectInput = { name: string; description: string };

function projectsPath(slug: string, projectId?: string) {
  const base = `/api/v1/workspaces/${encodeURIComponent(slug)}/projects/`;
  return projectId ? `${base}${encodeURIComponent(projectId)}/` : base;
}

export function getProjects(token: string, slug: string, page = 1) {
  return apiFetch<PaginatedProjects>(
    `${projectsPath(slug)}?${new URLSearchParams({ page: String(page) })}`,
    { token },
  );
}
export function createProject(token: string, slug: string, data: ProjectInput) {
  return apiFetch<Project>(projectsPath(slug), {
    token,
    method: "POST",
    body: JSON.stringify(data),
  });
}
export function getProject(token: string, slug: string, projectId: string) {
  return apiFetch<Project>(projectsPath(slug, projectId), { token });
}
export function updateProject(
  token: string,
  slug: string,
  projectId: string,
  data: Partial<ProjectInput>,
) {
  return apiFetch<Project>(projectsPath(slug, projectId), {
    token,
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
export function deleteProject(token: string, slug: string, projectId: string) {
  return apiFetch<null>(projectsPath(slug, projectId), {
    token,
    method: "DELETE",
  });
}
export function leaveProject(token: string, slug: string, projectId: string) {
  return apiFetch<null>(`${projectsPath(slug, projectId)}leave/`, {
    token,
    method: "POST",
  });
}
export function getProjectMembers(
  token: string,
  slug: string,
  projectId: string,
  page = 1,
) {
  return apiFetch<PaginatedProjectMembers>(
    `${projectsPath(slug, projectId)}members/?${new URLSearchParams({ page: String(page) })}`,
    { token },
  );
}
export function addProjectMember(
  token: string,
  slug: string,
  projectId: string,
  userId: number,
  role: ProjectRole,
) {
  return apiFetch<ProjectMember>(`${projectsPath(slug, projectId)}members/`, {
    token,
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}
export function updateProjectMemberRole(
  token: string,
  slug: string,
  projectId: string,
  membershipId: string,
  role: ProjectRole,
) {
  return apiFetch<ProjectMember>(
    `${projectsPath(slug, projectId)}members/${encodeURIComponent(membershipId)}/role/`,
    { token, method: "PATCH", body: JSON.stringify({ role }) },
  );
}
export function removeProjectMember(
  token: string,
  slug: string,
  projectId: string,
  membershipId: string,
) {
  return apiFetch<null>(
    `${projectsPath(slug, projectId)}members/${encodeURIComponent(membershipId)}/`,
    { token, method: "DELETE" },
  );
}

export type TaskStatus = "todo" | "in_progress" | "in_review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type Task = {
  comment_count: number;
  id: string;
  project: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: number | null;
  assignee_email: string | null;
  assignee_avatar: string | null;
  created_by: number | null;
  created_by_email: string | null;
  created_by_avatar: string | null;
  due_date: string | null;
  position: number;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};
export type TaskInput = Pick<
  Task,
  "title" | "description" | "status" | "priority" | "assignee" | "due_date"
>;
export type TaskOrdering =
  | "created_at"
  | "updated_at"
  | "due_date"
  | "title"
  | "priority"
  | "status"
  | "position";
export type TaskQuery = {
  page?: number;
  page_size?: number;
  status?: TaskStatus[];
  priority?: TaskPriority;
  assignee?: number | "me";
  search?: string;
  ordering?: TaskOrdering | `-${TaskOrdering}`;
  due_before?: string;
  overdue?: boolean;
};
export type PaginatedTasks = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Task[];
};

function tasksPath(slug: string, projectId: string, taskId?: string) {
  const base = `${projectsPath(slug, projectId)}tasks/`;
  return taskId ? `${base}${encodeURIComponent(taskId)}/` : base;
}
export function getTasks(
  token: string,
  slug: string,
  projectId: string,
  query: TaskQuery = {},
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (
      value !== undefined &&
      value !== "" &&
      (!Array.isArray(value) || value.length)
    ) {
      params.set(key, Array.isArray(value) ? value.join(",") : String(value));
    }
  }
  return apiFetch<PaginatedTasks>(`${tasksPath(slug, projectId)}?${params}`, {
    token,
  });
}
export function getTask(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
) {
  return apiFetch<Task>(tasksPath(slug, projectId, taskId), { token });
}
export function createTask(
  token: string,
  slug: string,
  projectId: string,
  data: TaskInput,
) {
  return apiFetch<Task>(tasksPath(slug, projectId), {
    token,
    method: "POST",
    body: JSON.stringify(data),
  });
}
export function updateTask(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  data: Partial<TaskInput>,
) {
  return apiFetch<Task>(tasksPath(slug, projectId, taskId), {
    token,
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
export function deleteTask(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
) {
  return apiFetch<null>(tasksPath(slug, projectId, taskId), {
    token,
    method: "DELETE",
  });
}
export function moveTask(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  status: TaskStatus,
  target: number | { before_task: string } | { placement: "first" | "last" },
) {
  return apiFetch<Task>(`${tasksPath(slug, projectId, taskId)}move/`, {
    token,
    method: "POST",
    body: JSON.stringify({
      status,
      ...(typeof target === "number" ? { position: target } : target),
    }),
  });
}

export type TaskComment = {
  id: string;
  task: string;
  author_id: number | null;
  author_name: string;
  reply_to: string | null;
  mentions: string[];
  attachment: { filename: string; size: number } | null;
  edited_at: string | null;
  body: string;
  created_at: string;
  updated_at: string;
};

export type PaginatedTaskComments = {
  count: number;
  next: string | null;
  previous: string | null;
  results: TaskComment[];
};

function taskCommentsPath(slug: string, projectId: string, taskId: string) {
  return `${tasksPath(slug, projectId, taskId)}comments/`;
}

export function getTaskComments(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  page = 1,
) {
  return apiFetch<PaginatedTaskComments>(
    `${taskCommentsPath(slug, projectId, taskId)}?page=${page}`,
    { token },
  );
}

export function createTaskComment(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  body: string,
  replyTo?: string,
  attachment?: File,
) {
  const payload = attachment ? new FormData() : null;
  if (payload && attachment) {
    payload.set("body", body);
    payload.set("attachment", attachment);
    if (replyTo) payload.set("reply_to", replyTo);
  }
  return apiFetch<TaskComment>(taskCommentsPath(slug, projectId, taskId), {
    token,
    method: "POST",
    body: payload ?? JSON.stringify({ body, ...(replyTo ? { reply_to: replyTo } : {}) }),
  });
}

export function updateTaskComment(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  commentId: string,
  body: string,
) {
  return apiFetch<TaskComment>(
    `${taskCommentsPath(slug, projectId, taskId)}${encodeURIComponent(commentId)}/`,
    { token, method: "PATCH", body: JSON.stringify({ body }) },
  );
}

export function deleteTaskComment(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  commentId: string,
) {
  return apiFetch<null>(
    `${taskCommentsPath(slug, projectId, taskId)}${encodeURIComponent(commentId)}/`,
    { token, method: "DELETE" },
  );
}


export function downloadCommentAttachment(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  commentId: string,
) {
  return apiFetch<Blob>(
    `${taskCommentsPath(slug, projectId, taskId)}${encodeURIComponent(commentId)}/attachment/`,
    { token, responseType: "blob" },
  );
}

export function updateResourceAvatar(token: string, slug: string, avatar: File | null): Promise<Workspace>;
export function updateResourceAvatar(token: string, slug: string, avatar: File | null, projectId: string): Promise<Project>;
export function updateResourceAvatar(
  token: string,
  slug: string,
  avatar: File | null,
  projectId?: string,
) {
  const path = projectId
    ? projectsPath(slug, projectId)
    : `/api/v1/workspaces/${encodeURIComponent(slug)}/`;
  const form = avatar ? new FormData() : null;
  if (form && avatar) form.set("avatar", avatar);
  return apiFetch<Workspace | Project>(path, {
    token,
    method: "PATCH",
    body: form ?? JSON.stringify({ avatar: null }),
  });
}

export type NotificationEvent =
  | "task_assigned"
  | "task_updated"
  | "task_reminder"
  | "comment_mentioned"
  | "comment_replied"
  | "workspace_invited"
  | "workspace_role_changed"
  | "project_member_added"
  | "project_role_changed";

export type InboxNotification = {
  id: string;
  event_type: NotificationEvent;
  actor_name: string | null;
  workspace_slug: string | null;
  workspace_name: string | null;
  project: string | null;
  project_name: string | null;
  task: string | null;
  task_title: string | null;
  payload: { role?: string; old_role?: string; new_role?: string };
  created_at: string;
  is_read: boolean;
};

export type NotificationFilter = "all" | "unread" | "read";

export const NOTIFICATION_PAGE_SIZE = 20;

const notificationsPath = "/api/v1/notifications/";

export function getNotifications(
  token: string,
  filter: NotificationFilter,
  page = 1,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(NOTIFICATION_PAGE_SIZE),
  });
  if (filter !== "all") query.set("read", String(filter === "read"));
  return apiFetch<{
    count: number;
    next: string | null;
    previous: string | null;
    results: InboxNotification[];
  }>(`${notificationsPath}?${query}`, { token, signal });
}

export function getUnreadNotificationCount(token: string, signal?: AbortSignal) {
  return apiFetch<{ unread_count: number }>(`${notificationsPath}unread-count/`, {
    token,
    signal,
  });
}

export function markNotificationRead(token: string, id: string) {
  return apiFetch<InboxNotification>(
    `${notificationsPath}${encodeURIComponent(id)}/mark-read/`,
    { token, method: "POST" },
  );
}

export function markAllNotificationsRead(token: string) {
  return apiFetch<{ updated_count: number }>(`${notificationsPath}mark-all-read/`, {
    token,
    method: "POST",
  });
}

export function acceptNotificationInvitation(token: string, id: string) {
  return apiFetch<void>(
    `${notificationsPath}${encodeURIComponent(id)}/accept-invitation/`,
    { token, method: "POST" },
  );
}

export type CalendarEventType = "event" | "meeting" | "deadline";

export type CalendarTimelineItem = {
  id: string;
  project: string;
  title: string;
  item_type: "event" | "task";
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  event_type: CalendarEventType | null;
  task_status: TaskStatus | null;
  task_priority: TaskPriority | null;
};

export type CalendarEventInput = {
  title: string;
  description: string;
  event_type: CalendarEventType;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
};

export type CalendarEvent = CalendarEventInput & { id: string; project: string };

function calendarPath(slug: string, projectId?: string) {
  const workspace = `/api/v1/workspaces/${encodeURIComponent(slug)}`;
  return projectId ? `${workspace}/projects/${encodeURIComponent(projectId)}/calendar/` : `${workspace}/calendar/`;
}

export function getCalendarTimeline(token: string, slug: string, start: string, end: string, projectId?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ start, end });
  return apiFetch<{ count: number; results: CalendarTimelineItem[] }>(
    `${calendarPath(slug, projectId)}timeline/?${query}`, { token, signal },
  );
}

export function getCalendarEvent(token: string, slug: string, projectId: string, id: string, signal?: AbortSignal) {
  return apiFetch<CalendarEvent>(`${calendarPath(slug, projectId)}${encodeURIComponent(id)}/`, { token, signal });
}

export function saveCalendarEvent(token: string, slug: string, projectId: string, data: CalendarEventInput, id?: string) {
  const path = calendarPath(slug, projectId);
  return apiFetch<CalendarEvent>(id ? `${path}${encodeURIComponent(id)}/` : path, {
    token, method: id ? "PATCH" : "POST", body: JSON.stringify(data),
  });
}

export function deleteCalendarEvent(token: string, slug: string, projectId: string, id: string) {
  return apiFetch<void>(`${calendarPath(slug, projectId)}${encodeURIComponent(id)}/`, { token, method: "DELETE" });
}

export type ReportFilters = {
  start_date?: string;
  end_date?: string;
  assignee?: string;
  status?: string;
  priority?: string;
};
export type ReportSummary = {
  total_tasks: number; completed_tasks: number; active_tasks: number;
  overdue_tasks: number; unassigned_tasks: number; completion_rate: number;
};
export type ReportOverview = {
  summary: ReportSummary;
  status_distribution: Record<TaskStatus, number>;
  priority_distribution: Record<TaskPriority, number>;
  as_of: string;
  member_workload?: { user_id: number; user_email: string }[];
};
export type ReportBucket = { date: string; start_date: string; end_date: string; created: number; completed: number };
export type ReportHistory = {
  start_date: string; end_date: string; completion_tracking_since: string | null;
  results: ReportBucket[]; previous_results: ReportBucket[];
};
export type ReportWorkload = {
  assignee: number | null; total_tasks: number; active_tasks: number; completed_tasks: number;
  overdue_tasks: number; due_soon_tasks: number; completion_rate: number;
};
export type ReportProject = { project_id: string; project_name: string; total_tasks: number; completed_tasks: number; overdue_tasks: number; completion_rate: number };
export type ReportRanking = { count: number; next: string | null; previous: string | null; results: ReportProject[] };

function reportPath(slug: string, projectId?: string) {
  const base = `/api/v1/workspaces/${encodeURIComponent(slug)}`;
  return projectId ? `${base}/projects/${encodeURIComponent(projectId)}/reports/` : `${base}/reports/`;
}
function reportQuery(filters: Record<string, string | undefined>) {
  return new URLSearchParams(Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1]))).toString();
}
export function getReportOverview(token: string, slug: string, projectId?: string, signal?: AbortSignal) {
  return apiFetch<ReportOverview>(reportPath(slug, projectId), { token, signal });
}
export function getReportHistory(token: string, slug: string, filters: ReportFilters & { granularity: string }, projectId?: string, signal?: AbortSignal) {
  return apiFetch<ReportHistory>(`${reportPath(slug, projectId)}history/?${reportQuery(filters)}`, { token, signal });
}
export function getReportWorkload(token: string, slug: string, filters: ReportFilters, projectId?: string, signal?: AbortSignal) {
  return apiFetch<ReportWorkload[]>(`${reportPath(slug, projectId)}workload/?${reportQuery(filters)}`, { token, signal });
}
export function getReportRanking(token: string, slug: string, filters: ReportFilters, page: number, ordering: string, signal?: AbortSignal) {
  return apiFetch<ReportRanking>(`${reportPath(slug)}projects/?${reportQuery({ ...filters, page: String(page), ordering })}`, { token, signal });
}
export function exportReport(token: string, slug: string, filters: ReportFilters, projectId?: string) {
  return apiFetch<Blob>(`${reportPath(slug, projectId)}export/?${reportQuery(filters)}`, { token, responseType: "blob" });
}

export type ChatConversation = {
  id: string; workspace: string; type: "project" | "direct"; project: string | null;
  direct_user_low: number | null; direct_user_high: number | null; updated_at: string;
};
export type ChatMessage = {
  id: string; conversation: string; sender_id: number | null; content: string; reply_to: string | null;
  attachments: { id: string; filename: string; size: number }[];
  created_at: string; edited_at: string | null; deleted_at: string | null;
};
export type ChatMessagePage = { count: number; next: string | null; previous: string | null; results: ChatMessage[] };
function chatsPath(slug: string, conversation?: string) {
  const base = `/api/v1/workspaces/${encodeURIComponent(slug)}/chats/`;
  return conversation ? `${base}${encodeURIComponent(conversation)}/messages/` : base;
}
export function getProjectChat(token: string, slug: string, project: string) {
  return apiFetch<ChatConversation>(`${projectsPath(slug, project)}chat/`, { token });
}
type PaginatedDirectChats = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ChatConversation[];
};
export function getDirectChats(token: string, slug: string): Promise<ChatConversation[]>;
export function getDirectChats(token: string, slug: string, page: number): Promise<PaginatedDirectChats>;
export function getDirectChats(token: string, slug: string, page?: number) {
  const path = `${chatsPath(slug)}direct/`;
  if (page === undefined) return apiFetch<ChatConversation[]>(path, { token });
  return apiFetch<PaginatedDirectChats>(
    `${path}?${new URLSearchParams({ page: String(page), page_size: "100" })}`,
    { token },
  );
}
export function startDirectChat(token: string, slug: string, recipient: number) {
  return apiFetch<ChatConversation>(`${chatsPath(slug)}direct/`, {
    token, method: "POST", body: JSON.stringify({ recipient_id: recipient }),
  });
}
export function getChatMessages(token: string, slug: string, conversation: string, page = 1, signal?: AbortSignal) {
  return apiFetch<ChatMessagePage>(`${chatsPath(slug, conversation)}?page=${page}`, { token, signal });
}
export function sendChatMessage(token: string, slug: string, conversation: string, content: string, reply: string | null, files: File[]) {
  const body = new FormData();
  body.set("content", content);
  if (reply) body.set("reply_to", reply);
  for (const file of files) body.append("attachments", file);
  return apiFetch<ChatMessage>(chatsPath(slug, conversation), { token, method: "POST", body });
}
export function editChatMessage(token: string, slug: string, conversation: string, message: string, content: string) {
  return apiFetch<ChatMessage>(`${chatsPath(slug, conversation)}${encodeURIComponent(message)}/`, {
    token, method: "PATCH", body: JSON.stringify({ content }),
  });
}
export function deleteChatMessage(token: string, slug: string, conversation: string, message: string) {
  return apiFetch<void>(`${chatsPath(slug, conversation)}${encodeURIComponent(message)}/`, { token, method: "DELETE" });
}
export function downloadChatAttachment(token: string, slug: string, conversation: string, message: string, attachment: string) {
  return apiFetch<Blob>(`${chatsPath(slug, conversation)}${encodeURIComponent(message)}/attachments/${encodeURIComponent(attachment)}/`, {
    token, responseType: "blob",
  });
}
export function chatWebSocketUrl(slug: string, conversation: string) {
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/chats/${encodeURIComponent(slug)}/${encodeURIComponent(conversation)}/`;
  url.search = "";
  url.hash = "";
  return url.toString();
}


export type ChatUnreadSummary = {
  unread_count: number;
  conversations: { id: string; project: string | null; recipient_id: number | null; unread_count: number }[];
};
export function getUnreadChats(token: string, slug: string, signal?: AbortSignal) {
  return apiFetch<ChatUnreadSummary>(`${chatsPath(slug)}unread/`, {token, signal});
}
export function markChatRead(token: string, slug: string, conversation: string, message: string) {
  return apiFetch<void>(`${chatsPath(slug)}${encodeURIComponent(conversation)}/read/`, {
    token, method: "POST", body: JSON.stringify({message_id: message}),
  });
}
export function getChatMessage(token: string, slug: string, conversation: string, message: string) {
  return apiFetch<ChatMessage>(`${chatsPath(slug, conversation)}${encodeURIComponent(message)}/`, {token});
}


export type TaskReminder = {
  id: string; kind: "absolute" | "relative"; timezone: string; run_at: string | null;
  days_before: number | null; local_time: string | null;
  status: "pending" | "disabled" | "invalid" | "sent" | "cancelled" | "failed";
  sent_at: string | null; last_error: string; attempts: number;
};
export type ReminderInput = {kind: "absolute" | "relative"; timezone: string; run_at?: string; days_before?: number; local_time?: string};
function reminderPath(slug: string, project: string, task: string, reminder?: string) {
  return `${projectsPath(slug, project)}tasks/${encodeURIComponent(task)}/reminders/${reminder ? encodeURIComponent(reminder) + "/" : ""}`;
}
export function getTaskReminders(token: string, slug: string, project: string, task: string, page = 1, signal?: AbortSignal) {
  return apiFetch<{results: TaskReminder[]; count: number; next: string | null}>(`${reminderPath(slug, project, task)}?page=${page}`, {token, signal});
}
export function saveTaskReminder(token: string, slug: string, project: string, task: string, input: ReminderInput, reminder?: string) {
  return apiFetch<TaskReminder>(reminderPath(slug, project, task, reminder), {token, method: reminder ? "PATCH" : "POST", body: JSON.stringify(input)});
}
export function cancelTaskReminder(token: string, slug: string, project: string, task: string, reminder: string) {
  return apiFetch<void>(reminderPath(slug, project, task, reminder), {token, method: "DELETE"});
}
