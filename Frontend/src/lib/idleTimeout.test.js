import { test } from "node:test";
import assert from "node:assert/strict";
import { IDLE_LOGOUT_KEY, LAST_ACTIVITY_KEY, checkIdle, idleMessage, isIdle, startIdleWatch } from "./idleTimeout.js";
import { IDLE_TIMEOUT_MINUTES } from "./securityConfig.js";

// A localStorage stand-in shared by "tabs" (localStorage is shared by every tab of one origin).
function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k),
    keys: () => [...data.keys()].sort(),
  };
}
const MIN = 60000;

test("default is off (0): today's behaviour, no watching at all", () => {
  assert.equal(IDLE_TIMEOUT_MINUTES, 0);
  assert.equal(isIdle(1, 10 * 24 * 60 * MIN, 0), false);
  const stop = startIdleWatch(0, () => assert.fail("must not log out"));
  assert.equal(typeof stop, "function"); // returns without touching window or timers
  stop();
});

test("idle only after the full time without activity", () => {
  assert.equal(isIdle(1000, 1000 + 15 * MIN - 1, 15), false);
  assert.equal(isIdle(1000, 1000 + 15 * MIN, 15), true);
});

test("the message uses the setting", () => {
  assert.equal(idleMessage(15), "You were logged out after 15 minutes of inactivity.");
  assert.equal(idleMessage(1), "You were logged out after 1 minute of inactivity.");
});

test("idle logout clears only the session keys and leaves the reason for every tab", () => {
  const store = memoryStorage({ token: "t", role: "manager", username: "ZZTEST", [LAST_ACTIVITY_KEY]: "1000", other: "kept" });
  assert.equal(checkIdle(store, 1000 + 15 * MIN, 15), "idle");
  assert.deepEqual(store.keys(), [IDLE_LOGOUT_KEY, "other"]);
  assert.equal(store.getItem(IDLE_LOGOUT_KEY), "15");
});

test("activity in one tab keeps the other tabs logged in (shared lastActivity)", () => {
  const shared = memoryStorage({ token: "t", [LAST_ACTIVITY_KEY]: "0" });
  shared.setItem(LAST_ACTIVITY_KEY, String(10 * MIN)); // tab A: the user moved the mouse at 10 min
  assert.equal(checkIdle(shared, 20 * MIN, 15), null); // tab B checks at 20 min: still logged in
  assert.equal(shared.getItem("token"), "t");
  assert.equal(checkIdle(shared, 25 * MIN, 15), "idle");
});

test("a tab whose session another tab ended for inactivity follows it to the Login page", () => {
  const shared = memoryStorage({ [IDLE_LOGOUT_KEY]: "15" });
  assert.equal(checkIdle(shared, 1, 15), "gone");
  assert.equal(checkIdle(memoryStorage(), 1, 15), null); // logged out by hand: nothing to do
});

test("a session with no recorded activity starts counting now instead of logging out", () => {
  const store = memoryStorage({ token: "t" });
  assert.equal(checkIdle(store, 5 * MIN, 15), null);
  assert.equal(store.getItem(LAST_ACTIVITY_KEY), String(5 * MIN));
});
