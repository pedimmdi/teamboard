import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ConnectionManager from "./connection-manager";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function AiConnectionsPage() {
  if (process.env.TEAMBOARD_MCP_UI !== "1" && process.env.TEAMBOARD_MCP_LOCAL_UI !== "1") notFound();
  return <ConnectionManager />;
}
