import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/website";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard", "/dashboard/", "/login", "/register", "/accept-invitation", "/forgot-password", "/reset-password", "/resend-verification", "/verify-email"],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
