import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  reactProductionProfiling: process.env.NEXT_PUBLIC_TEAMBOARD_PROFILE_UI === "1",
  allowedDevOrigins: ["127.0.0.1"],
  async headers() {
    return [
      "/dashboard/:path*",
      "/:flow(login|register|forgot-password|reset-password|resend-verification|verify-email|accept-invitation)",
    ].map((source) => ({
      source,
      headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
    }));
  },
};

export default nextConfig;
