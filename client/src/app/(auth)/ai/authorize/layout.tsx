import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AI connection",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ConsentLayout({ children }: { children: ReactNode }) {
  if (process.env.TEAMBOARD_MCP_UI !== "1" && process.env.TEAMBOARD_MCP_LOCAL_UI !== "1") notFound();
  return children;
}
