import assert from "node:assert/strict";
import test from "node:test";
import { loadSource } from "./load-source.mjs";

function loadModule(path, globals = {}, dependencies = {}) {
  return loadSource(path, {
    URL, AbortSignal, process: { env: {} }, ...globals,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected import ${name}`);
      return dependencies[name];
    },
  });
}

test("twenty simultaneous public reads share one anonymous request per locale and expired articles are refreshed", async () => {
  let now = 1;
  const cache = loadModule("../src/lib/website-cache.ts", { Date: { now: () => now } });
  const requests = [];
  let status = 200;
  const website = loadModule("../src/lib/website-data.ts", {
    fetch: async (url, options) => {
      requests.push({ url, options });
      return new Response(JSON.stringify({ title: new URL(url).searchParams.get("lang") }), { status });
    },
  }, { "server-only": {}, "@/lib/website-cache": cache });

  const english = await Promise.all(Array.from({ length: 20 }, () => website.post("an-article", "en")));
  assert.ok(english.every((item) => item.title === "en"));
  assert.equal(requests.length, 1);
  assert.equal((await website.post("an-article", "fa")).title, "fa");
  assert.equal(requests.length, 2);
  assert.equal(requests[0].options.credentials, "omit");
  assert.equal(requests[0].options.cache, "no-store");
  assert.equal(requests[0].options.headers, undefined);

  now += 30_000;
  status = 404;
  await assert.rejects(website.post("an-article", "en"), /404/);
  await assert.rejects(website.post("an-article", "en"), /404/);
  assert.equal(requests.length, 4);
});

test("public cache evicts old keys and coalesces only within its bounded capacity", async () => {
  const { createTimedReadCache } = loadModule("../src/lib/website-cache.ts");
  const read = createTimedReadCache(60_000, 2);
  assert.equal(await read("first", async () => 1), 1);
  assert.equal(await read("second", async () => 2), 2);
  assert.equal(await read("third", async () => 3), 3);
  assert.equal(await read("second", async () => 20), 2);
  assert.equal(await read("first", async () => 10), 10);
});

test("sitemap uses the last complete snapshot when a later page fails and restores static URLs after expiry", async () => {
  let now = 1;
  let failure = "all";
  let refreshes = 0;
  const cache = loadModule("../src/lib/website-cache.ts", { Date: { now: () => now } });
  const website = loadModule("../src/lib/website.ts");
  const sitemap = loadModule("../src/app/sitemap.ts", {}, {
    "@/lib/website": website,
    "@/lib/website-cache": cache,
    "@/lib/website-data": {
      async sitemapPage(cursor) {
        if (!cursor) {
          refreshes += 1;
          if (failure === "all") throw new Error("upstream down");
          return {
            results: [{ slug: failure === "later" ? "partial" : "translated", has_persian_translation: true }],
            next: "https://api.example.test/sitemap/?cursor=second",
          };
        }
        if (failure) throw new Error("next page failed");
        assert.equal(cursor, "second");
        return { results: [{ slug: "english", has_persian_translation: false }], next: null };
      },
    },
  });
  const read = sitemap.default;
  const locationList = (data) => Array.from(data, ({ url }) => new URL(url).pathname);
  const core = await read();
  assert.equal(core.length, 14);
  assert.ok(locationList(core).includes("/fa/contact"));
  assert.ok(locationList(core).includes("/mcp"));
  assert.ok(locationList(core).includes("/fa/mcp"));
  await read();
  assert.equal(refreshes, 1);

  now += 15_000;
  failure = "";
  const [first, other] = await Promise.all([read(), read()]);
  assert.equal(refreshes, 2);
  assert.deepEqual(locationList(first), locationList(other));
  assert.ok(locationList(first).includes("/fa/blog/translated"));
  assert.ok(locationList(first).includes("/blog/english"));
  assert.ok(!locationList(first).includes("/fa/blog/english"));

  now += 5 * 60_000;
  failure = "later";
  const stale = await read();
  assert.deepEqual(locationList(stale), locationList(first));
  assert.ok(!locationList(stale).includes("/blog/partial"));

  now += 60 * 60_000;
  assert.deepEqual(locationList(await read()), locationList(core));
});

test("public privacy copy uses the configured day count in both languages and avoids guessing on failure", async () => {
  const { retentionSchedule } = loadModule("../src/lib/website-copy.ts");
  assert.match(retentionSchedule("en", 45), /45 days/);
  assert.match(retentionSchedule("en", 1), /1 day\./);
  assert.match(retentionSchedule("fa", 45), /۴۵ روز/);
  assert.doesNotMatch(retentionSchedule("en", null), /\d/);
  assert.doesNotMatch(retentionSchedule("fa", null), /[۰-۹]/);
});
