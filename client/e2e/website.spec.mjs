import {test,expect} from "@playwright/test";
test("public website is accessible, searchable and supports safe articles and contact recovery",async({page,request})=>{
 test.setTimeout(120000);
 await page.addInitScript(()=>{
   window.websiteMetrics={lcp:null,cls:0};
   try {new PerformanceObserver(list=>{for(const entry of list.getEntries())window.websiteMetrics.lcp=entry.startTime;}).observe({type:"largest-contentful-paint",buffered:true});
   new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.websiteMetrics.cls+=entry.value;}).observe({type:"layout-shift",buffered:true});} catch {}
 });
 await page.goto("/");
 await expect(page.getByRole("heading",{level:1})).toContainText("Ship together");
 await expect(page.getByRole("navigation",{name:"Main navigation"})).toBeVisible();
 await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content",/TeamBoard/);
 console.log("landing_lab_metrics",await page.evaluate(()=>({paint:window.websiteMetrics,dom_ready_ms:performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd,js_transfer_bytes:performance.getEntriesByType("resource").filter(r=>r.name.includes(".js")).reduce((sum,r)=>sum+r.encodedBodySize,0)})));
 await page.setViewportSize({width:390,height:844});
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:"test-results/website-home-mobile.png",fullPage:true});
 await page.setViewportSize({width:1440,height:900});
 await page.screenshot({path:"test-results/website-home-desktop.png",fullPage:true});
 await page.goto("/blog");
 await expect(page.getByRole("article")).toHaveCount(10);
 await page.getByRole("link",{name:"Next →",exact:true}).click();
 await expect(page).toHaveURL(/page=2/);
 await expect(page.getByRole("article")).toHaveCount(1);
 await page.goto("/blog/website-0");
 await expect(page.getByRole("heading",{name:"A clearer workflow"})).toBeVisible();
 expect(await page.evaluate(()=>window.websiteUnsafe)).toBeUndefined();
 await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
 await page.goto("/blog/nonexistent-website-post");
 await expect(page.getByRole("heading",{name:"404"})).toBeVisible();
 await page.goto("/contact");
 for(const [label,value] of [["Your name","Website tester"],["Email address","website@example.com"],["Subject","Test enquiry"],["Message","A browser test enquiry."]])await page.getByLabel(label,{exact:true}).fill(value);
 let code=400;
 await page.route("**/api/v1/website/contact/",route=>route.fulfill({status:code,headers:{"Retry-After":"60","Access-Control-Expose-Headers":"Retry-After"},contentType:"application/json",body:JSON.stringify({email:["Check your email address."]})}));
 for(const [status,message] of [[400,"highlighted"],[413,"too large"],[429,"wait 60 seconds"]]){code=status;await page.getByRole("button",{name:"Send message",exact:true}).click();await expect(page.locator("form").getByRole("alert")).toContainText(message);await expect(page.getByLabel("Your name")).toHaveValue("Website tester");}
 await page.unroute("**/api/v1/website/contact/");
 await page.getByRole("button",{name:"Send message",exact:true}).click();
 await expect(page.locator("form").getByRole("status")).toContainText("has been received");
 await page.setViewportSize({width:390,height:844});
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:"test-results/website-contact-mobile.png",fullPage:true});
 const robots=await request.get("/robots.txt");expect(await robots.text()).toContain("/dashboard/");
 const sitemap=await request.get("/sitemap.xml");expect(sitemap.ok()).toBe(true);expect(await sitemap.text()).toContain("/blog/website-0");
});

test("public translations have independent SEO and readable desktop and mobile layouts", async ({ page, request }) => {
  test.setTimeout(120_000);
  const landing = await request.get("/fa");
  expect(landing.ok()).toBe(true);
  expect(await landing.text()).toMatch(/<html[^>]*lang="fa"[^>]*dir="rtl"/);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Dark mode" }).click();
  await page.getByRole("link", { name: "Switch to Persian" }).click();
  await expect(page).toHaveURL(/\/fa$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("با هم پیش ببرید");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/fa$/);
  await expect.poll(async () => {
    const href = await page.locator('link[hreflang="en"]').getAttribute("href");
    return new URL(href).pathname;
  }).toBe("/");
  await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "fa_IR");
  await page.screenshot({ path: "test-results/website-fa-desktop-dark.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  for (const [path, title] of [
    ["/fa", "با هم پیش ببرید"],
    ["/fa/about", "کار تیمی خوب"],
    ["/fa/blog", "ایده‌هایی برای کار تیمی بهتر"],
    ["/fa/blog/website-0", "اولین نوشته تیم‌برد"],
    ["/fa/contact", "چطور می‌توانیم کمک کنیم؟"],
    ["/fa/privacy", "سیاست حریم خصوصی"],
    ["/fa/terms", "شرایط استفاده"],
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(title);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }

  await page.goto("/fa/blog/website-0");
  await expect(page.getByRole("heading", { name: "روالی روشن‌تر" })).toBeVisible();
  await expect(page.locator('link[hreflang="en"]')).toHaveAttribute("href", /\/blog\/website-0$/);
  await page.getByRole("link", { name: "تغییر زبان به انگلیسی" }).click();
  await expect(page).toHaveURL(/\/blog\/website-0$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { name: "A clearer workflow" })).toBeVisible();
  await expect(page.locator('link[hreflang="fa"]')).toHaveAttribute("href", /\/fa\/blog\/website-0$/);

  await page.goto("/fa/blog/website-1");
  await expect(page.getByText("این نوشته فعلاً به زبان انگلیسی در دسترس است.")).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await expect(page.locator('link[hreflang="fa"]')).toHaveCount(0);

  const sitemap = await request.get("/sitemap.xml");
  const xml = await sitemap.text();
  expect(xml).toContain("/fa/blog/website-0");
  expect(xml).not.toContain("/fa/blog/website-1");
  expect(xml).toContain('hreflang="fa"');
});

test("direct Persian visitors can submit contact forms and retain RTL into login", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/fa/contact");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByLabel("نام شما")).toBeVisible();
  await expect(page.getByLabel("نشانی ایمیل")).toHaveAttribute("dir", "ltr");
  for (const [label, value] of [["نام شما", "آزمایش تیم‌برد"], ["نشانی ایمیل", "fa@example.com"], ["موضوع", "پرسش درباره تیم‌برد"], ["پیام", "این یک پیام آزمایشی است."]]) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.route("**/api/v1/website/contact/", (route) => route.fulfill({ status: 429, headers: { "Retry-After": "60", "Access-Control-Expose-Headers": "Retry-After" } }));
  await page.getByRole("button", { name: "ارسال پیام" }).click();
  await expect(page.locator("form").getByRole("alert")).toContainText("۶۰ ثانیه");
  await expect(page.getByLabel("نام شما")).toHaveValue("آزمایش تیم‌برد");
  await page.unroute("**/api/v1/website/contact/");
  await page.route("**/api/v1/website/contact/", (route) => route.fulfill({ status: 201, contentType: "application/json", body: "{}" }));
  await page.getByRole("button", { name: "ارسال پیام" }).click();
  await expect(page.locator("form").getByRole("status")).toContainText("پیامتان دریافت شد");
  await page.screenshot({ path: "test-results/website-fa-contact-mobile.png", fullPage: true });
  await page.getByRole("link", { name: "ورود", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});
