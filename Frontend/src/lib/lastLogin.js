// The "Last login" notice shown once after a successful login (IAS2, backend LOGIN_AUDIT=true).
// The login response's last_login ({at: UTC ISO time, ip}) is kept in sessionStorage until closed.
export const LAST_LOGIN_KEY = "lastLogin";
export const NOT_YOU_TEXT = "Not you?";
export const CHANGE_NOW_TEXT = "Change your password now.";

// timeZone only for tests; the page uses the browser's own time zone.
export function lastLoginText(lastLogin, timeZone) {
  const when = new Date(lastLogin.at).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  });
  return `Last login: ${when} from ${lastLogin.ip}`;
}

// What login.jsx keeps after a successful login: only a usable last_login, else nothing.
export function storedLastLogin(responseData) {
  const last = responseData?.last_login;
  return last && typeof last.at === "string" && typeof last.ip === "string" ? JSON.stringify(last) : null;
}
