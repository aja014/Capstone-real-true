import { test } from "node:test";
import assert from "node:assert/strict";
import { CHANGE_NOW_TEXT, NOT_YOU_TEXT, lastLoginText, storedLastLogin } from "./lastLogin.js";
import {
  PASSWORD_CHANGED_TEXT, SESSION_EXPIRED_KEY, SESSION_EXPIRED_TEXT, forgetLoginNotice, loginNotice,
  readLoginNotice, reasonFor401,
} from "./logoutReason.js";
import { IDLE_LOGOUT_KEY } from "./idleTimeout.js";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) };
}

test("last login text: the previous login's time (local time zone) and IP", () => {
  assert.equal(lastLoginText({ at: "2026-10-08T07:42:00Z", ip: "203.0.113.5" }, "Asia/Manila"),
    "Last login: Oct 8, 2026, 3:42 PM from 203.0.113.5");
  assert.equal(NOT_YOU_TEXT + " " + CHANGE_NOW_TEXT, "Not you? Change your password now.");
});

test("the notice is kept only when the backend sent a usable last_login", () => {
  assert.equal(storedLastLogin({ access_token: "x", role: "admin" }), null); // switch off: today's response
  assert.equal(storedLastLogin({ last_login: null }), null);                 // first login
  assert.equal(storedLastLogin({ last_login: { at: "2026-10-08T07:42:00Z", ip: "203.0.113.5" } }),
    '{"at":"2026-10-08T07:42:00Z","ip":"203.0.113.5"}');
});

test("Login page: a session ended by a password change says so, not 'session expired'", () => {
  assert.equal(reasonFor401("Your password was changed. Please log in again."), "password_changed");
  assert.equal(loginNotice(reasonFor401("Your password was changed. Please log in again."), null), PASSWORD_CHANGED_TEXT);
  assert.equal(PASSWORD_CHANGED_TEXT, "Your password was changed. Please log in again.");
});

test("Login page: any other 401 keeps today's 'session expired' text", () => {
  assert.equal(reasonFor401("Invalid or expired token"), "1");
  assert.equal(reasonFor401(undefined), "1");
  assert.equal(loginNotice("1", null), SESSION_EXPIRED_TEXT);
  assert.equal(SESSION_EXPIRED_TEXT, "Your session has expired. Please log in again.");
  assert.equal(loginNotice(null, null), null);
});

test("Login page: the idle logout message wins and stays for the other tabs", () => {
  const session = memoryStorage({ [SESSION_EXPIRED_KEY]: "1" });
  const local = memoryStorage({ [IDLE_LOGOUT_KEY]: "15" });
  assert.equal(readLoginNotice(session, local), "You were logged out after 15 minutes of inactivity.");
  forgetLoginNotice(session);
  assert.equal(session.getItem(SESSION_EXPIRED_KEY), null);
  assert.equal(local.getItem(IDLE_LOGOUT_KEY), "15"); // removed only by the next successful login
});
