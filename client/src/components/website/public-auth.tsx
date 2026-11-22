"use client";
import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
export function HomeSession() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/dashboard");
  }, [isLoading, isAuthenticated, router]);
  return null;
}
export function PublicAuth() {
  const { isAuthenticated, isLoading } = useAuth();
  return isAuthenticated ? (
    <Link href="/dashboard">Open dashboard →</Link>
  ) : (
    <>
      <Link href="/login">Log in</Link>
      <Link href="/register">Get started</Link>
      {isLoading && (
        <span
          style={{
            position: "absolute",
            width: 1,
            height: 1,
            overflow: "hidden",
            clipPath: "inset(50%)",
          }}
          role="status"
        >
          Checking session
        </span>
      )}
    </>
  );
}
