import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_HEADER, publicLocale } from "@/lib/locale";

export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.set(LOCALE_HEADER, publicLocale(request.nextUrl.pathname) ?? "en");
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/", "/about", "/contact", "/blog/:path*", "/mcp", "/privacy", "/terms", "/fa/:path*"],
};
