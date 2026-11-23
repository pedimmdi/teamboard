import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function checkAccessibility(page, region) {
  let scan = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  if (region) scan = scan.include(region);
  const { violations } = await scan.analyze();
  expect(violations.map(({ id, nodes }) => ({ id, elements: nodes.map((node) => node.target) }))).toEqual([]);
}

test("public forms expose keyboard focus and accessible names in every language and theme", async ({ page, context, baseURL }) => {
  test.setTimeout(60_000);
  for (const locale of ["en", "fa"]) {
    for (const theme of ["light", "dark"]) {
      await test.step(`${locale}/${theme}`, async () => {
        await page.setViewportSize({ width: theme === "dark" ? 390 : 1440, height: 900 });
        await context.addCookies([{ name: "teamboard-theme", value: theme, url: baseURL }]);
        await page.goto(locale === "fa" ? "/fa/contact" : "/contact");
        await expect(page.locator("html")).toHaveAttribute("lang", locale);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.keyboard.press("Tab");
        const skip = page.locator('a[href="#public-content"]');
        await expect(skip).toBeFocused();
        await page.keyboard.press("Enter");
        const name = locale === "fa" ? "نشانی ایمیل" : "Email address";
        await expect(page.getByRole("textbox", { name })).toBeVisible();
        expect(await page.getByRole("main").ariaSnapshot()).toContain(name);
        await checkAccessibility(page);
      });
    }
  }
});

for (const [locale, theme, width] of [["en", "light", 1440], ["fa", "dark", 390]]) {
  test(`heavy Tasks and Dashboard remain usable with accessible dialogs in ${locale}/${theme}`, async ({ page, context, baseURL }, info) => {
    test.setTimeout(100_000);
    const fa = locale === "fa";
    const label = (en, persian) => fa ? persian : en;
    await page.setViewportSize({ width, height: 900 });
    await context.addCookies([
      { name: "teamboard-locale", value: locale, url: baseURL },
      { name: "teamboard-theme", value: theme, url: baseURL },
    ]);
    await page.goto("/login");
    await page.getByLabel(label("Email address", "نشانی ایمیل"), { exact: true }).fill("browser-quality@example.com");
    await page.locator('input[autocomplete="current-password"]').fill(process.env.E2E_PASSWORD);
    await page.getByRole("button", { name: label("Sign in", "ورود"), exact: true }).click();
    await expect(page.getByText(label("My tasks today", "کارهای امروز من"), { exact: true })).toBeVisible();
    const metric = async () => page.evaluate(() => {
      const commits = performance.getEntriesByName("teamboard:dashboard-render").map((entry) => entry.duration).sort((a, b) => a - b);
      return { commits: commits.length, p95: commits[Math.ceil(0.95 * commits.length) - 1] ?? null, max: commits.at(-1) ?? null };
    });
    const dashboard = await metric();
    await page.goto("/dashboard/workspaces/uiquality/projects");
    await page.getByRole("link", { name: /UI quality project/ }).filter({ visible: true }).first().click();
    await expect(page.getByRole("button", { name: /Quality task/ }).filter({ visible: true }).first()).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    const trigger = page.getByRole("button", { name: label("New task", "کار جدید"), exact: true }).filter({ visible: true }).first();
    await trigger.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: label("New task", "کار جدید"), exact: true });
    await expect(dialog).toBeVisible();
    expect(await dialog.ariaSnapshot()).toContain(label("New task", "کار جدید"));
    for (let index = 0; index < 8; index++) {
      await page.keyboard.press(index < 4 ? "Tab" : "Shift+Tab");
      expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
    }
    await checkAccessibility(page, '[role="dialog"]');
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    const tasks = await metric();
    if (process.env.NEXT_PUBLIC_TEAMBOARD_PROFILE_UI === "1") {
      expect(dashboard.commits).toBeGreaterThan(0);
      expect(tasks.commits).toBeGreaterThan(0);
      console.log(`ui_profile ${locale}/${theme}`, { dashboard, tasks });
    }
    await page.screenshot({ path: info.outputPath("tasks.png") });
  });
}
