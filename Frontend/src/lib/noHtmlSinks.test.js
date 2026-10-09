import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// XSS guard (IAS2 injection testing): React escapes every value it renders, so stored text such as
// "<script>" shows as text. That only holds while no code writes raw HTML; this test fails if any
// source file starts to. (FloodRiskModal's L.divIcon html is a fixed SVG with no data in it.)
const SRC = join(import.meta.dirname, "..");
const SINKS = [/dangerouslySetInnerHTML/, /\.innerHTML\s*=/, /\.outerHTML\s*=/, /insertAdjacentHTML/,
  /document\.write/, /\.bindPopup\(/, /\.bindTooltip\(/, /\beval\(/, /new Function\(/];

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.(jsx?|tsx?)$/.test(name) && !name.endsWith(".test.js") ? [path] : [];
  });
}

test("no source file writes raw HTML (React escaping is never bypassed)", () => {
  const hits = files(SRC).flatMap((path) => {
    const text = readFileSync(path, "utf8");
    return SINKS.filter((re) => re.test(text)).map((re) => `${path}: ${re}`);
  });
  assert.deepEqual(hits, []);
});

test("the only divIcon HTML is the fixed marker SVG (no ${} data in it)", () => {
  const text = readFileSync(join(SRC, "components", "FloodRiskModal.jsx"), "utf8");
  const html = text.match(/html:\s*`([^`]*)`/);
  assert.ok(html, "divIcon html not found");
  assert.equal(html[1].includes("${"), false);
});
