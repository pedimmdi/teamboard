import { expect, test } from "@playwright/test";

test("public MCP guides have bilingual SEO, usable FAQ, and no invented server URL", async ({ page, baseURL }) => {
  const response = await page.goto("/mcp");
  expect(response.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "AI integrations with MCP" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Local preview" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy URL" })).toHaveCount(0);
  await expect(page.locator("link[rel=canonical]")).toHaveAttribute("href", /\/mcp$/);
  await expect(page.locator('link[hreflang="fa"]')).toHaveAttribute("href", /\/fa\/mcp$/);

  await page.setViewportSize({ width: 360, height: 800 });
  await page.context().addCookies([{ name: "teamboard-theme", value: "dark", url: baseURL }]);
  await page.goto("/fa/mcp");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { name: "اتصال به هوش مصنوعی با MCP" })).toBeVisible();
  await expect(page.locator("link[rel=canonical]")).toHaveAttribute("href", /\/fa\/mcp$/);
  await expect(page.getByRole("heading", { name: "Gemini Apps" })).toBeVisible();
  const faq = page.locator("summary").first();
  await faq.focus();
  await expect(faq).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("details[open]")).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
