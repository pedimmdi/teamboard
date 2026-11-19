"use client";

import ReportsView from "@/components/reports/reports-view";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";

export default function ReportsPage() {
  const { slug } = useWorkspace();
  const { project } = useProjectContext();
  return <ReportsView slug={slug} projectId={project.id} />;
}
