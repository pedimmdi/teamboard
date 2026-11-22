import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { direction } from "@/lib/locale";
import { PreferencesProvider } from "@/lib/preferences";
import { getPreferences } from "@/lib/server-preferences";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "TeamBoard", template: "%s | TeamBoard" },
  description: "Plan projects, coordinate tasks, and keep your team in sync with TeamBoard.",
  applicationName: "TeamBoard",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { locale, preferredLocale, theme } = await getPreferences();
  return (
    <html lang={locale} dir={direction(locale)} data-theme={theme}
      data-iran-sans={process.env.IRANSANSX_WEBFONT === "1" ? "" : undefined}>
      <body>
        <PreferencesProvider initialLocale={locale} preferredLocale={preferredLocale} initialTheme={theme}>
          <AuthProvider>{children}</AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
