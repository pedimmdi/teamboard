"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";

import type { Organization } from "@/lib/api";

type OrganizationContextValue = {
  organization: Organization;
  updateOrganization: (organization: Organization) => void;
};

const OrganizationContext =
  createContext<OrganizationContextValue | null>(null);

export function OrganizationProvider({
  organization,
  updateOrganization,
  children,
}: {
  organization: Organization;
  updateOrganization: (organization: Organization) => void;
  children: ReactNode;
}) {
  return (
    <OrganizationContext.Provider
      value={{ organization, updateOrganization }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganizationContext() {
  const context = useContext(OrganizationContext);

  if (!context) {
    throw new Error(
      "Organization context must be used inside OrganizationProvider.",
    );
  }

  return context;
}

export function useOrganization() {
  return useOrganizationContext().organization;
}
