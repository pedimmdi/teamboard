import { expect, test } from "@playwright/test";

async function expectNoHorizontalOverflow(page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

test("authentication screens retain Persian and dark mode on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/login");
  const document = page.locator("html");

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(document).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Switch to Persian" }).click();
  await page.getByRole("button", { name: "حالت تیره" }).click();
  await expect(document).toHaveAttribute("lang", "fa");
  await expect(document).toHaveAttribute("dir", "rtl");
  await expect(document).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("نشانی ایمیل")).toHaveAttribute("dir", "ltr");

  const password = page.getByLabel("گذرواژه", { exact: true });
  await page.getByRole("button", { name: "نمایش گذرواژه" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "پنهان کردن گذرواژه" }).click();
  await expect(password).toHaveAttribute("type", "password");

  await page.route("**/api/v1/accounts/login/", async (route) => {
    const headers = {
      "Access-Control-Allow-Origin": new URL(page.url()).origin,
      "Access-Control-Allow-Credentials": "true",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    await route.fulfill({
      status: 401,
      headers,
      json: { detail: "No active account found with the given credentials." },
    });
  });
  await page.getByLabel("نشانی ایمیل").fill("wrong@example.com");
  await password.fill("not-the-password");
  await page.getByRole("button", { name: "ورود", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toContainText("ایمیل یا گذرواژه درست نیست.");
  await page.unroute("**/api/v1/accounts/login/");

  await page.getByRole("link", { name: "گذرواژه را فراموش کرده‌اید؟" }).click();
  await expect(page.getByRole("heading", { name: "گذرواژه‌تان را فراموش کرده‌اید؟" })).toBeVisible();
  await page.reload();
  await expect(document).toHaveAttribute("dir", "rtl");
  await expect(document).toHaveAttribute("data-theme", "dark");

  for (const [route, heading] of [
    ["/register", "حساب کاربری بسازید"],
    ["/resend-verification", "پیوند تأیید جدید بگیرید"],
    ["/reset-password", "گذرواژه جدید تعیین کنید"],
    ["/verify-email", "تأیید ایمیل انجام نشد"],
    ["/accept-invitation", "امکان استفاده از این دعوت وجود ندارد"],
  ]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});

test("account and workspace navigation support both layouts in Persian dark mode", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/login");
  await page.getByLabel("Email address").fill("browser-reminder@example.com");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/workspaces\/[^/]+\/dashboard$/);

  await page.getByRole("button", { name: "Switch to Persian" }).click();
  await page.getByRole("button", { name: "حالت تیره" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const workspaceNav = page.getByRole("navigation", { name: "فضای کاری", exact: true });
  await workspaceNav.getByRole("link", { name: "نمایه", exact: true }).click();
  await expect(page.getByRole("heading", { name: "نمایه", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 390, height: 844 });
  const account = page.getByRole("navigation", { name: "ناوبری حساب کاربری" });
  await account.getByRole("link", { name: "امنیت" }).click();
  await expect(page.getByLabel("گذرواژه فعلی", { exact: true })).toBeVisible();
  await account.getByRole("link", { name: "نشست‌ها" }).click();
  await expect(page.getByRole("heading", { name: "نشست‌های فعال" })).toBeVisible();
  await expect(page.getByText("این دستگاه", { exact: true })).toBeVisible();
  await page.getByRole("banner").getByRole("link", { name: /^اعلان‌ها/ }).click();
  await expect(page.getByRole("heading", { name: "اعلان‌ها" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByText("بیشتر", { selector: "summary" }).click();
  const more = page.getByRole("navigation", { name: "گزینه‌های فضای کاری" });
  await expect(more.getByRole("link", { name: "گزارش‌ها" })).toBeVisible();
  await expect(more.getByRole("link", { name: "اعضا" })).toBeVisible();
  await expect(more.getByRole("link", { name: "تنظیمات" })).toBeVisible();
  await more.getByRole("link", { name: "گزارش‌ها" }).click();
  await expect(page).toHaveURL(/\/reports$/);
  await expect(more).not.toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expectNoHorizontalOverflow(page);
});
