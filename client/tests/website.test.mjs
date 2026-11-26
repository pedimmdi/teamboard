import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import Markdown from "react-markdown";
import { loadSource } from "./load-source.mjs";

const website = loadSource("../src/lib/website.ts", { process: { env: {} } });

test("public Markdown rendering rejects raw HTML and unsafe link protocols", () => {
  const html = renderToStaticMarkup(React.createElement(Markdown, { skipHtml: true },
    "## Heading\n\n<script>alert(1)</script>\n\n[attack](javascript:alert(1))"));
  assert.match(html, /<h2>Heading<\/h2>/);
  assert.doesNotMatch(html, /<script|href="javascript:/);
});

test("public metadata is canonical and structured data cannot break out of its script", () => {
  const output = website.jsonLd({ headline: "</script><script>alert(1)</script>" });
  assert.doesNotMatch(output, /</);
  assert.equal(JSON.parse(output).headline, "</script><script>alert(1)</script>");

  const meta = website.publicMetadata("Title", "Description", "/blog?page=2", "en", false);
  assert.equal(meta.alternates.canonical, "/blog?page=2");
  assert.equal(meta.openGraph.url, "/blog?page=2");
  assert.equal(meta.alternates.languages, undefined);
  assert.equal(meta.twitter.images[0].alt, "TeamBoard");
});

test("articles with optional excerpts still have localized descriptions", () => {
  assert.equal(website.articleDescription("A clearer workflow", " A preview ", "en"), "A preview");
  assert.equal(website.articleDescription("A clearer workflow", "", "en"), "Read “A clearer workflow” on the TeamBoard blog.");
  assert.equal(website.articleDescription("روالی روشن‌تر", "  ", "fa"), "روالی روشن‌تر را در وبلاگ تیم‌برد بخوانید.");
});

test("Persian pages are self-canonical with reciprocal language metadata", () => {
  const meta = website.publicMetadata("وبلاگ تیم‌برد", "نوشته‌های تیم‌برد", "/blog", "fa");
  assert.equal(meta.alternates.canonical, "/fa/blog");
  assert.equal(meta.alternates.languages.en, "/blog");
  assert.equal(meta.alternates.languages.fa, "/fa/blog");
  assert.equal(meta.alternates.languages["x-default"], "/blog");
  assert.equal(meta.openGraph.locale, "fa_IR");
  assert.equal(meta.openGraph.alternateLocale[0], "en_US");
});
