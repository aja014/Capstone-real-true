// The hosting headers (vercel.json) and security.txt that answer the IAS2 Scan 1 findings.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const vercel = JSON.parse(readFileSync(new URL("../../vercel.json", import.meta.url), "utf8"));
const rule = vercel.headers.find((h) => h.source === "/(.*)");
const header = (key) => rule.headers.find((h) => h.key === key)?.value;
const csp = Object.fromEntries(header("Content-Security-Policy").split(";").map((d) => {
  const [name, ...values] = d.trim().split(/\s+/);
  return [name, values];
}));

test("the headers apply to every path and the SPA rewrite is kept", () => {
  assert.ok(rule);
  assert.deepEqual(vercel.rewrites, [{ source: "/(.*)", destination: "/index.html" }]);
});

test("simple security headers", () => {
  assert.equal(header("X-Content-Type-Options"), "nosniff");
  assert.equal(header("Referrer-Policy"), "strict-origin-when-cross-origin");
  assert.equal(header("X-Frame-Options"), "DENY");
  assert.equal(header("Permissions-Policy"), "camera=(), microphone=(), geolocation=()");
});

test("CSP allows only what the app loads", () => {
  assert.deepEqual(csp["default-src"], ["'self'"]);
  assert.deepEqual(csp["script-src"], ["'self'"]);
  assert.deepEqual(csp["style-src"], ["'self'"]);
  assert.deepEqual(csp["img-src"], ["'self'", "data:", "https://server.arcgisonline.com"]);  // GIS View tiles
  assert.deepEqual(csp["connect-src"], ["'self'", "https://firemap-api-91u5.onrender.com"]);
  assert.deepEqual(csp["object-src"], ["'none'"]);
  assert.deepEqual(csp["base-uri"], ["'self'"]);
  assert.deepEqual(csp["frame-ancestors"], ["'none'"]);
});

test("CSP has no unsafe keywords and no CDN", () => {
  const value = header("Content-Security-Policy");
  assert.doesNotMatch(value, /unsafe-inline|unsafe-eval|unpkg|\*/);
});

test("security.txt", () => {
  // Windows checkouts (core.autocrlf) turn the committed LF into CRLF; the content is what counts.
  const text = readFileSync(new URL("../../public/.well-known/security.txt", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  assert.equal(text,"Contact: mailto:gaj@firemap.local\nExpires: 2027-10-08T00:00:00.000Z\nPreferred-Languages: en\n");
});
