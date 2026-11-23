import { getLocale } from "@/lib/server-preferences";
import { RouteFeedback } from "@/components/route-feedback";

export default async function NotFound() {
  const locale = await getLocale();
  return (
    <main>
      <RouteFeedback
        title={locale === "fa" ? "۴۰۴ — صفحه پیدا نشد" : "404 — Page not found"}
        description={locale === "fa" ? "این نشانی وجود ندارد یا صفحه جابه‌جا شده است." : "This address doesn’t exist or the page has moved."}
      />
    </main>
  );
}
