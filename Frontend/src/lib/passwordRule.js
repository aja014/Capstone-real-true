// Same rule and messages as the backend's password_rule_error() in app/security.py.
// The backend is the real check; this only saves a round trip.

export const PASSWORD_HINT = "At least 8 characters, including 2 letters";
export const PASSWORD_RULE_MESSAGE =
  "Password must be at least 8 characters and include at least 2 letters.";
export const PASSWORD_TOO_LONG_MESSAGE =
  "Password must be at most 72 characters (accented characters count as 2).";

// Returns null if the password is acceptable as a NEW password, else the message.
export function passwordRuleError(password) {
  if (new TextEncoder().encode(password).length > 72) return PASSWORD_TOO_LONG_MESSAGE;
  const letters = (password.match(/[A-Za-z]/g) || []).length;
  // [...password] counts characters the way Python's len() does (emoji = 1, not 2)
  if ([...password].length < 8 || letters < 2) return PASSWORD_RULE_MESSAGE;
  return null;
}
