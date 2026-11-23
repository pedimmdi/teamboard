"use client";

import { Profiler, type ProfilerOnRenderCallback, type ReactNode } from "react";

const recordCommit: ProfilerOnRenderCallback = (_id, phase, actualDuration, _baseDuration, startTime) => {
  performance.measure("teamboard:dashboard-render", { start: startTime, duration: actualDuration, detail: { phase } });
};

export function DashboardProfiler({ children }: { children: ReactNode }) {
  if (process.env.NEXT_PUBLIC_TEAMBOARD_PROFILE_UI !== "1") return children;
  return <Profiler id="Dashboard" onRender={recordCommit}>{children}</Profiler>;
}
