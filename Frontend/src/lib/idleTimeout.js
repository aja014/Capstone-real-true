// Idle logout (IAS2, VITE_IDLE_TIMEOUT_MINUTES). Activity in ANY tab is written to localStorage
// ("lastActivity"), which all tabs share, so one active tab keeps the others logged in.
import { clearSession } from "./session.js";

export const LAST_ACTIVITY_KEY = "lastActivity";
// Left in localStorage after an idle logout so every open tab (and the Login page) can show why.
export const IDLE_LOGOUT_KEY = "idleLogout";
export const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "wheel", "scroll"];
const WRITE_EVERY_MS = 5000;
const CHECK_EVERY_MS = 10000;

export function isIdle(lastActivity, now, minutes) {
  return minutes > 0 && lastActivity > 0 && now - lastActivity >= minutes * 60000;
}

export function idleMessage(minutes) {
  return `You were logged out after ${minutes} ${Number(minutes) === 1 ? "minute" : "minutes"} of inactivity.`;
}

export function markActivity(storage = localStorage, now = Date.now()) {
  storage.setItem(LAST_ACTIVITY_KEY, String(now));
}

// One check: "idle" = this tab logged out now, "gone" = another tab already logged out for
// inactivity, null = nothing to do. Touches only `storage`, so it is unit-tested.
export function checkIdle(storage, now, minutes) {
  if (!storage.getItem("token")) return storage.getItem(IDLE_LOGOUT_KEY) ? "gone" : null;
  const last = Number(storage.getItem(LAST_ACTIVITY_KEY)) || 0;
  if (!last) {
    markActivity(storage, now); // logged in before any tab started watching
    return null;
  }
  if (!isIdle(last, now, minutes)) return null;
  clearSession(storage);
  storage.setItem(IDLE_LOGOUT_KEY, String(minutes));
  return "idle";
}

// Starts watching this tab and returns the stop function. onLogout runs when this tab must go
// to the Login page.
export function startIdleWatch(minutes, onLogout) {
  if (!(minutes > 0)) return () => {};
  let lastWrite = 0;
  const onActivity = () => {
    const now = Date.now();
    if (now - lastWrite < WRITE_EVERY_MS || !localStorage.getItem("token")) return;
    lastWrite = now;
    markActivity(localStorage, now);
  };
  const tick = () => {
    if (checkIdle(localStorage, Date.now(), minutes)) onLogout();
  };
  ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
  const timer = setInterval(tick, CHECK_EVERY_MS);
  return () => {
    clearInterval(timer);
    ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
  };
}
