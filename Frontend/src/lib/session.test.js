import { test } from "node:test";
import assert from "node:assert/strict";
import { usernameFromToken } from "./session.js";

// A made-up token: only its middle (payload) part is read; header and signature are dummies.
function fakeToken(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  const b64url = btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `x.${b64url}.y`;
}

test("returns the stored username from the token, not the typed one", () => {
  assert.equal(usernameFromToken(fakeToken({ sub: "ZZTEST Juliet", role: "admin" }), "zztest juliet"), "ZZTEST Juliet");
});

test("non-ASCII names survive (UTF-8)", () => {
  assert.equal(usernameFromToken(fakeToken({ sub: "ZZTEST Ordoñez" }), "typed"), "ZZTEST Ordoñez");
});

test("a broken or missing token, or no sub, falls back to the typed name", () => {
  assert.equal(usernameFromToken("not-a-token", "typed"), "typed");
  assert.equal(usernameFromToken(undefined, "typed"), "typed");
  assert.equal(usernameFromToken(fakeToken({ role: "admin" }), "typed"), "typed");
});
