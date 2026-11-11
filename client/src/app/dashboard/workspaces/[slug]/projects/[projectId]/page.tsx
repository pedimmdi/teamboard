import { redirect } from "next/navigation";

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ slug: string; projectId: string }>;
}) {
  const { slug, projectId } = await params;
  redirect(
    `/dashboard/workspaces/${encodeURIComponent(slug)}/projects/${encodeURIComponent(projectId)}/tasks`,
  );
}
