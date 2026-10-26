import { test } from "node:test";
import assert from "node:assert/strict";
import { looksLikeCode, noticeText, normalizeCode, requestErrorMessage } from "./recoveryCode.js";

// Made-up codes only.
test("normalizes like the backend: no dashes, no spaces, upper case", () => {
  assert.equal(normalizeCode(" abcd-efgh jkmn "), "ABCDEFGHJKMN");
  assert.equal(normalizeCode(null), "");
});

test("accepts 12 code characters with or without dashes", () => {
  assert.ok(looksLikeCode("ABCD-EFGH-JKMN"));
  assert.ok(looksLikeCode("abcdefghjkmn"));
});

test("refuses wrong length and letters the code never uses", () => {
  assert.ok(!looksLikeCode("ABCD-EFGH-JKM"));
  assert.ok(!looksLikeCode("ABCD-EFGH-JKM0"));   // 0
  assert.ok(!looksLikeCode("ABCD-EFGH-JKMI"));   // I
  assert.ok(!looksLikeCode(""));
});

test("notice text reads the UTC time and the IP", () => {
  const text = noticeText({ occurred_at: "2026-10-26T03:15:00", ip_address: "127.0.0.1" }, "Asia/Manila");
  assert.equal(text, "Your recovery code was changed on Oct 26, 2026, 11:15 AM from 127.0.0.1.");
});

test("notice text without an IP", () => {
  const text = noticeText({ occurred_at: "2026-10-26T03:15:00", ip_address: null }, "UTC");
  assert.equal(text, "Your recovery code was changed on Oct 26, 2026, 3:15 AM.");
});

test("request errors: backend text, field list, no server, fallback", () => {
  assert.equal(requestErrorMessage({ response: { data: { detail: "Invalid username or recovery code" } } }, "x"),
    "Invalid username or recovery code");
  assert.equal(requestErrorMessage({ response: { data: { detail: [{ loc: ["body", "username"], msg: "Field required" }] } } }, "x"),
    "username: Field required");
  assert.equal(requestErrorMessage({}, "x"), "Cannot reach the server. Please try again.");
  assert.equal(requestErrorMessage({ response: { data: {} } }, "Could not save"), "Could not save");
});
