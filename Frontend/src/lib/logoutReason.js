// Why the Login page is showing: set by the 401 handler (api/api.js) in sessionStorage, or by
// the idle logout in localStorage (shared, so every open tab can show it).
import { IDLE_LOGOUT_KEY, idleMessage } from "./idleTimeout.js";

export const SESSION_EXPIRED_KEY = "sessionExpired";
// Same text as the backend's SESSION_ENDED_MESSAGE (the 401 detail after a password change).
export const PASSWORD_CHANGED_TEXT = "Your password was changed. Please log in again.";
export const SESSION_EXPIRED_TEXT = "Your session has expired. Please log in again.";

// The value the 401 handler stores, from the backend's 401 detail.
export function reasonFor401(detail) {
  return detail === PASSWORD_CHANGED_TEXT ? "password_changed" : "1";
}

// The notice for the Login page, or null.
export function loginNotice(sessionReason, idleMinutes) {
  if (idleMinutes) return idleMessage(idleMinutes);
  if (sessionReason === "password_changed") return PASSWORD_CHANGED_TEXT;
  if (sessionReason) return SESSION_EXPIRED_TEXT;
  return null;
}

// The Login page reads the notice when it opens (no side effects: React may run it twice)…
export function readLoginNotice(session = sessionStorage, local = localStorage) {
  return loginNotice(session.getItem(SESSION_EXPIRED_KEY), local.getItem(IDLE_LOGOUT_KEY));
}

// …and then forgets the 401 reason, so a reload doesn't show it again. The idle marker stays
// until the next successful login: other open tabs still need it to follow to the Login page.
export function forgetLoginNotice(session = sessionStorage) {
  session.removeItem(SESSION_EXPIRED_KEY);
}

export function forgetIdleLogout(local = localStorage) {
  local.removeItem(IDLE_LOGOUT_KEY);
}
