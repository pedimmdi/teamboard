"use client";

import ReportsView from "@/components/reports/reports-view";
import { useWorkspace } from "../workspace-context";

export default function ReportsPage() {
  const { slug, role } = useWorkspace();
  return <ReportsView workspaceRole={role} slug={slug} />;
}
