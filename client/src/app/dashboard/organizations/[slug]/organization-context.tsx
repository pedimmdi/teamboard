
"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

import type { Organization } from "@/lib/api";

type OrganizationContextValue = {
  organization: Organization;
};

const OrganizationContext =
  createContext<OrganizationContextValue | null>(null);

export function OrganizationProvider({
  organization,
  children,
}: {
  organization: Organization;
  children: ReactNode;
}) {
  return (
    <OrganizationContext.Provider value={{ organization }}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization() {
  const context = useContext(OrganizationContext);

  if (!context) {
    throw new Error(
      "useOrganization must be used inside OrganizationProvider.",
    );
  }

  return context.organization;
}
