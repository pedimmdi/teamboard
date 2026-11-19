"use client";

import ReportsView from "@/components/reports/reports-view";
import { useWorkspace } from "../workspace-context";

export default function ReportsPage() {
  const { slug } = useWorkspace();
  return <ReportsView slug={slug} />;
}
