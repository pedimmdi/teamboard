import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import Markdown from "react-markdown";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import ts from "typescript";
test("public Markdown rendering rejects raw HTML and unsafe link protocols",()=>{
 const html=renderToStaticMarkup(React.createElement(Markdown,{skipHtml:true},'## Heading\n\n<script>alert(1)</script>\n\n[attack](javascript:alert(1))'));
 assert.match(html,/<h2>Heading<\/h2>/);
 assert.doesNotMatch(html,/<script|href="javascript:/);
});
test("public metadata is canonical and structured data cannot break out of its script",()=>{
 const exports={};
 runInNewContext(ts.transpileModule(readFileSync(new URL("../src/lib/website.ts",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,process:{env:{}}});
 const output=exports.jsonLd({headline:"</script><script>alert(1)</script>"});
 assert.doesNotMatch(output, /</);
 assert.equal(JSON.parse(output).headline,"</script><script>alert(1)</script>");
 const meta=exports.publicMetadata("Title","Description","/blog?page=2");
 assert.equal(meta.alternates.canonical,"/blog?page=2");
 assert.equal(meta.openGraph.url,"/blog?page=2");
});
