"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();

  const {
    user,
    isAuthenticated,
    isLoading,
    logout,
  } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated || !user) {
    return null;
  }

  return (
    <main style={{ padding: "40px" }}>
      <h1>Dashboard</h1>

      <p style={{ marginTop: "12px" }}>
        Welcome,{" "}
        {user.first_name || user.email}.
      </p>

      <button
        type="button"
        onClick={async () => {
          await logout();
          router.replace("/login");
        }}
        style={{
          marginTop: "24px",
          padding: "10px 16px",
          cursor: "pointer",
        }}
      >
        Sign out
      </button>
    </main>
  );
}