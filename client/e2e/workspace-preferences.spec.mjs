import { expect, test } from "@playwright/test";

const workspace = "/dashboard/workspaces/chatunread";
const workspaceViews = [
  ["dashboard", "Dashboard", "داشبورد"],
  ["projects", "Projects", "پروژه‌ها"],
  ["calendar", "Calendar", "تقویم"],
  ["chats", "Chats", "گفت‌وگوها"],
  ["reports", "Reports", "گزارش‌ها"],
  ["members", "Members", "اعضا"],
  ["invitations", "Invitations", "دعوت‌نامه‌ها"],
  ["settings", "Settings", "تنظیمات"],
];
const projectViews = [
  ["tasks", "New task", "کار جدید"],
  ["calendar", "Calendar", "تقویم"],
  ["chat", "Chats", "گفت‌وگوها"],
  ["reports", "Reports", "گزارش‌ها"],
  ["members", "Members", "اعضا"],
  ["settings", "Project details", "جزئیات پروژه"],
];

async function expectReflow(page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

for (const locale of ["en", "fa"]) {
  for (const theme of ["light", "dark"]) {
    test(`workspace and project routes render in ${locale}/${theme} on desktop and mobile`, async ({ page, context, baseURL }, info) => {
      test.setTimeout(150_000);
      const isPersian = locale === "fa";
      const label = (english, persian) => isPersian ? persian : english;
      await context.addCookies([
        { name: "teamboard-locale", value: locale, url: baseURL },
        { name: "teamboard-theme", value: theme, url: baseURL },
      ]);
      await page.goto("/login");
      const root = page.locator("html");
      await expect(root).toHaveAttribute("lang", locale);
      await expect(root).toHaveAttribute("dir", isPersian ? "rtl" : "ltr");
      await expect(root).toHaveAttribute("data-theme", theme);
      await expect(root).toHaveCSS("color-scheme", theme);
      if (isPersian && process.env.IRANSANSX_WEBFONT === "1") {
        const loaded = await page.evaluate(async () => {
          const fonts = await document.fonts.load('400 16px "IranSansX"', "تیم‌برد");
          return fonts.some((font) => font.status === "loaded");
        });
        expect(loaded).toBe(true);
      }
      await page.getByLabel(label("Email address", "نشانی ایمیل"), { exact: true }).fill("browser-test@example.com");
      await page.locator('input[autocomplete="current-password"]').fill(process.env.E2E_PASSWORD);
      await page.getByRole("button", { name: label("Sign in", "ورود"), exact: true }).click();
      await expect(page).toHaveURL(/\/dashboard/);

      await page.goto(`${workspace}/projects`);
      const project = page.getByRole("link", { name: "Unread project" }).filter({ visible: true }).first();
      await expect(project).toBeVisible();
      const href = await project.getAttribute("href");
      expect(href).toMatch(/\/projects\/[\w-]+(?:\/tasks)?$/);
      const projectBase = href.replace(/\/tasks$/, "");

      for (const [scope, base, views] of [["workspace", workspace, workspaceViews], ["project", projectBase, projectViews]]) {
        for (const [route, english, persian] of views) {
          await test.step(`${scope} ${route}`, async () => {
            await page.setViewportSize({ width: 1440, height: 900 });
            const response = await page.goto(`${base}/${route}`);
            expect(response.headers()["x-robots-tag"]).toContain("noindex");
            await expect(root).toHaveAttribute("lang", locale);
            await expect(root).toHaveAttribute("data-theme", theme);
            const role = route === "tasks" ? "button" : "heading";
            const target = page.getByRole(role, { name: label(english, persian), exact: true }).filter({ visible: true }).first();
            await expect(target).toBeVisible();
            if (route === "dashboard") {
              await expect(page.getByText(label("My tasks today", "کارهای امروز من"), { exact: true })).toBeVisible();
            }
            await expectReflow(page);
            if (route === "dashboard" && isPersian && theme === "dark") {
              await page.screenshot({ path: info.outputPath("workspace-desktop.png") });
            }
            await page.setViewportSize({ width: 390, height: 844 });
            await expect(target).toBeVisible();
            await expectReflow(page);
            if (route === "dashboard" && isPersian && theme === "dark") {
              await page.screenshot({ path: info.outputPath("workspace-mobile.png") });
            }
          });
        }
      }
    });
  }
}
