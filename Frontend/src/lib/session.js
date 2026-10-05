// The username to show in Settings: the stored spelling ("Aaron James"), not what was typed
// at login ("aaron james"). The backend puts the users-row username in the login token's
// "sub" claim; the token's middle part is plain base64url JSON, so reading it needs no secret
// and nothing else in it is used. Any problem → the typed name, as before.
export function usernameFromToken(token, fallback) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(part.padEnd(Math.ceil(part.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
    const sub = JSON.parse(new TextDecoder().decode(bytes)).sub;
    return typeof sub === "string" && sub.trim() ? sub : fallback;
  } catch {
    return fallback;
  }
}
