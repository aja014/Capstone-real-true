import { test } from "node:test";
import assert from "node:assert/strict";
import { TOO_MANY_ATTEMPTS, loginErrorMessage } from "./loginErrors.js";

test("429 shows the failed-login limit message", () => {
  assert.equal(TOO_MANY_ATTEMPTS, "Too many failed login attempts. Please try again in 5 minutes.");
  assert.equal(loginErrorMessage({ response: { status: 429 } }), TOO_MANY_ATTEMPTS);
});

test("the other login errors keep their messages", () => {
  assert.equal(loginErrorMessage({ response: { status: 401 } }), "Invalid username or password");
  assert.equal(loginErrorMessage({}), "Can't reach the server. Please try again.");
  assert.equal(loginErrorMessage({ response: { status: 500 } }), "Something went wrong on the server. Please try again.");
});
