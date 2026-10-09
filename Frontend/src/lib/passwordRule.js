// Same rule and messages as the backend's password_rule_error() in app/security.py.
// The backend is the real check; this only saves a round trip. The common-password list is
// checked by the backend only (its message shows in the form's red box).
import { PASSWORD_BLOCK_COMMON, PASSWORD_MIN_LENGTH } from "./securityConfig.js";

const DEFAULTS = { minLength: PASSWORD_MIN_LENGTH, blockCommon: PASSWORD_BLOCK_COMMON };

export const PASSWORD_TOO_LONG_MESSAGE =
  "Password must be at most 72 characters (accented characters count as 2).";
export const PASSWORD_HAS_USERNAME_MESSAGE = "Password must not contain your username.";

export function passwordRuleMessage(minLength = DEFAULTS.minLength) {
  return `Password must be at least ${minLength} characters and include at least 2 letters.`;
}

export function passwordHint({ minLength, blockCommon } = DEFAULTS) {
  const base = `At least ${minLength} characters, including 2 letters`;
  return blockCommon ? `${base}. Not a common password, and not your username.` : base;
}

export const PASSWORD_RULE_MESSAGE = passwordRuleMessage();
export const PASSWORD_HINT = passwordHint();

// Case-insensitive: the whole username without spaces (3+ characters), or one word of it
// with 4+ characters (the same test as the backend's _contains_username()).
export function containsUsername(password, username) {
  const name = (username || "").trim().toLowerCase();
  const parts = [name.replace(/ /g, ""), ...name.split(/\s+/).filter((w) => w.length >= 4)];
  const pw = password.toLowerCase();
  return parts.some((p) => p.length >= 3 && pw.includes(p));
}

// Returns null if the password is acceptable as a NEW password, else the message.
export function passwordRuleError(password, username = "", { minLength, blockCommon } = DEFAULTS) {
  if (new TextEncoder().encode(password).length > 72) return PASSWORD_TOO_LONG_MESSAGE;
  const letters = (password.match(/[A-Za-z]/g) || []).length;
  // [...password] counts characters the way Python's len() does (emoji = 1, not 2)
  if ([...password].length < minLength || letters < 2) return passwordRuleMessage(minLength);
  if (blockCommon && containsUsername(password, username)) return PASSWORD_HAS_USERNAME_MESSAGE;
  return null;
}
