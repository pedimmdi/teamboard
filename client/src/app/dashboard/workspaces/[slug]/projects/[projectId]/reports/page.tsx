"use client";

import ReportsView from "@/components/reports/reports-view";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";

export default function ReportsPage() {
  const { slug, role } = useWorkspace();
  const { project } = useProjectContext();
  return <ReportsView workspaceRole={role} slug={slug} projectId={project.id} />;
}
