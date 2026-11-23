import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));
const arabicScript = /\p{Script=Arabic}/u;
const literalLabels = new Set(["title", "placeholder", "aria-label"]);
const languageNeutral = new Set(["UTC", "· TXT, PNG, JPEG", "person@example.com", "you@example.com"]);

function parse(path) {
  return ts.createSourceFile(path, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true);
}

function visit(node, callback) {
  callback(node);
  ts.forEachChild(node, (child) => visit(child, callback));
}

function files(path) {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const child = join(path, entry.name);
    return entry.isDirectory() ? files(child) : /\.tsx?$/.test(entry.name) ? [child] : [];
  });
}

const catalog = new Map();
visit(parse(join(sourceRoot, "lib/workspace-locale.ts")), (node) => {
  if (ts.isVariableDeclaration(node) && node.name.getText() === "persian" && ts.isObjectLiteralExpression(node.initializer)) {
    for (const entry of node.initializer.properties) {
      assert.ok(ts.isPropertyAssignment(entry) && ts.isStringLiteral(entry.initializer));
      const key = ts.isStringLiteral(entry.name) || ts.isIdentifier(entry.name) ? entry.name.text : entry.name.getText();
      assert.ok(!catalog.has(key), `Duplicate translation: ${key}`);
      catalog.set(key, entry.initializer.text);
    }
  }
});

test("workspace copy has Persian translations and preserves interpolation placeholders", () => {
  assert.ok(catalog.size > 100);
  const placeholders = (text) => [...text.matchAll(/\{\d+\}/g)].map((m) => m[0]).sort();
  for (const [key, value] of catalog) {
    if (/[A-Za-z]{2,}/.test(key)) assert.match(value, arabicScript, key);
    assert.deepEqual(placeholders(value), placeholders(key), key);
  }
});

test("dashboard, auth, calendar, chat and reports calls resolve to Persian UI messages", () => {
  const roots = ["app/dashboard", "app/(auth)", "components/auth", "components/calendar", "components/chats", "components/reports"];
  const missing = [];
  for (const path of roots.flatMap((name) => files(join(sourceRoot, name)))) {
    const source = parse(path);
    visit(source, (node) => {
      const literal = ts.isJsxText(node) ? node.getText().trim() :
        ts.isJsxAttribute(node) && literalLabels.has(node.name.getText()) && node.initializer && ts.isStringLiteral(node.initializer)
          ? node.initializer.text : "";
      if (/[A-Za-z]{2,}/.test(literal) && !languageNeutral.has(literal)) {
        const { line } = source.getLineAndCharacterOfPosition(node.getStart());
        missing.push(`${relative(sourceRoot, path)}:${line + 1} Unlocalized JSX: ${literal}`);
      }
      if (!ts.isCallExpression(node) || !ts.isIdentifier(node.expression)) return;
      const [english, persian] = node.arguments;
      if (!english || !ts.isStringLiteralLike(english) || !/[A-Za-z]{2,}/.test(english.text)) return;
      const call = node.expression.text;
      if ((call === "ui" && !catalog.has(english.text)) ||
        (call === "t" && (!persian || (ts.isStringLiteralLike(persian) && !arabicScript.test(persian.text))))) {
        const { line } = source.getLineAndCharacterOfPosition(node.getStart());
        missing.push(`${relative(sourceRoot, path)}:${line + 1} ${english.text}`);
      }
    });
  }
  assert.deepEqual(missing, []);
});
