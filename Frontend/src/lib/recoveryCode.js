// Recovery codes (Forgot password). The backend is the real check; these only shape what the
// screens show. A code is never stored in localStorage or sessionStorage.

export const NO_CODE_HELP =
  "No recovery code? Admin & Finance: ask the Manager to reset your password. Manager: contact the system administrator.";

// Same comparison as the backend's normalize_code(): no dashes, no spaces, upper case.
export function normalizeCode(code) {
  return (code || "").replace(/[\s-]/g, "").toUpperCase();
}

// 12 characters from the code alphabet (no 0/O, 1/I/L), typed with or without dashes.
export function looksLikeCode(code) {
  return /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{12}$/.test(normalizeCode(code));
}

// occurred_at comes from the backend in UTC without a zone ("2026-10-26T03:15:00").
export function formatEventTime(occurredAt, timeZone) {
  const iso = /[zZ]|[+-]\d\d:\d\d$/.test(occurredAt) ? occurredAt : `${occurredAt}Z`;
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  });
}

// The "Not you?" notice after a code change, a reset with the code, or a Manager reset.
export function noticeText(notice, timeZone) {
  const from = notice.ip_address ? ` from ${notice.ip_address}` : "";
  return `Your recovery code was changed on ${formatEventTime(notice.occurred_at, timeZone)}${from}.`;
}

// The message for a failed request: the backend's text when it sent one, else a general line.
export function requestErrorMessage(error, fallback) {
  if (!error?.response) return "Cannot reach the server. Please try again.";
  const detail = error.response.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join(" ");
  return fallback;
}
