import { ApiError, getWorkspace, getWorkspaces } from "@/lib/api";

export function dashboardWorkspaceKey(userId: number) {
  return `teamboard:workspace:${userId}`;
}

export async function loadDashboardWorkspace(
  token: string,
  routeSlug?: string,
  savedSlug?: string | null,
) {
  const slug = routeSlug || savedSlug;
  if (slug) {
    try {
      return await getWorkspace(token, slug);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error;
      if (routeSlug) return null;
    }
  }
  const workspaces = await getWorkspaces(token);
  return workspaces.results[0] ?? null;
}
