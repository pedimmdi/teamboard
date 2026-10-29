"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

import type { Workspace } from "@/lib/api";

type WorkspaceContextValue = {
  workspace: Workspace;
  updateWorkspace: (workspace: Workspace) => void;
};

const WorkspaceContext =
  createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({
  workspace,
  updateWorkspace,
  children,
}: {
  workspace: Workspace;
  updateWorkspace: (workspace: Workspace) => void;
  children: ReactNode;
}) {
  return (
    <WorkspaceContext.Provider
      value={{ workspace, updateWorkspace }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext);

  if (!context) {
    throw new Error(
      "Workspace context must be used inside WorkspaceProvider.",
    );
  }

  return context;
}

export function useWorkspace() {
  return useWorkspaceContext().workspace;
}
