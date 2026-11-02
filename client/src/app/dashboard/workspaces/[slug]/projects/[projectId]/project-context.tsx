"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Project } from "@/lib/api";

const ProjectContext = createContext<{
  project: Project;
  updateProject: (project: Project) => void;
} | null>(null);

export function ProjectProvider({
  project,
  updateProject,
  children,
}: {
  project: Project;
  updateProject: (project: Project) => void;
  children: ReactNode;
}) {
  return (
    <ProjectContext.Provider value={{ project, updateProject }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProjectContext() {
  const context = useContext(ProjectContext);
  if (!context)
    throw new Error("Project context must be used inside ProjectProvider.");
  return context;
}
