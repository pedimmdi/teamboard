import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

function tokens(block) {
  return Object.fromEntries([...block.matchAll(/--([\w-]+): (#\w{6});/g)].map(([, name, color]) => [name, color]));
}

function luminance(hex) {
  const channels = hex.slice(1).match(/../g).map((pair) => Number.parseInt(pair, 16) / 255);
  const [r, g, b] = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const light = tokens(css.split(":root {")[1].split("}")[0]);
const dark = { ...light, ...tokens(css.split(':root[data-theme="dark"] {')[1].split("}")[0]) };

for (const [theme, palette] of Object.entries({ light, dark })) {
  test(`${theme} text and status tokens meet WCAG AA contrast`, () => {
    const surfaces = ["background", "surface", "surface-subtle", "surface-raised"];
    const pairs = [
      ...surfaces.flatMap((surface) => ["foreground", "text-secondary", "muted", "primary"].map((text) => [text, surface])),
      ["primary-foreground", "primary"],
      ["primary-foreground", "primary-hover"],
      ["primary", "primary-soft"],
      ["accent", "accent-soft"],
      ["text-on-brand", "brand-panel"],
      ["text-on-panel-muted", "brand-panel-accent"],
      ...["danger", "success", "warning", "info", "violet"].map((state) => [state, `${state}-background`]),
    ];
    for (const [foreground, background] of pairs) {
      const [low, high] = [luminance(palette[foreground]), luminance(palette[background])].sort((a, b) => a - b);
      const contrast = (high + 0.05) / (low + 0.05);
      assert.ok(contrast >= 4.5, `${foreground} on ${background} has ${contrast.toFixed(2)}:1 contrast`);
    }
  });
}
