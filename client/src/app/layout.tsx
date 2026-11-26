import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { direction } from "@/lib/locale";
import { persianFontAssets } from "@/lib/persian-font";
import { PreferencesProvider } from "@/lib/preferences";
import { getPreferences } from "@/lib/server-preferences";

const inter = localFont({
  src: "../../public/fonts/open/inter-latin-wght-normal.woff2",
  weight: "100 900",
  display: "swap",
  variable: "--font-inter",
});

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
  const font = persianFontAssets();
  // This licensed stylesheet is installed into the deployment's runtime static assets.
  // eslint-disable-next-line @next/next/no-css-tags
  const fontStylesheet = font.stylesheet ? <link rel="stylesheet" href="/fonts/iransansx/faces.css" precedence="default" /> : null;
  return (
    <html lang={locale} dir={direction(locale)} data-theme={theme} className={inter.variable}
      data-iran-sans={font.enabled ? "" : undefined}>
      <body>
        {locale === "fa" && font.regularHref && (
          <link rel="preload" as="font" type="font/woff2" href={font.regularHref} crossOrigin="anonymous" />
        )}
        {fontStylesheet}
        <PreferencesProvider initialLocale={locale} preferredLocale={preferredLocale} initialTheme={theme}>
          <AuthProvider>{children}</AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
