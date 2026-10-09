// IAS2 build-time switches (Vercel). Unset = today's local behaviour. `?? {}` lets the pure
// helpers that import this run under `node --test`, where import.meta.env doesn't exist.
const env = import.meta.env ?? {};

// Minutes without mouse, keyboard or touch activity before logout; 0 = off.
export const IDLE_TIMEOUT_MINUTES = Math.max(0, Number(env.VITE_IDLE_TIMEOUT_MINUTES) || 0);
// Same values as the backend's PASSWORD_MIN_LENGTH / PASSWORD_BLOCK_COMMON (Render).
export const PASSWORD_MIN_LENGTH = Number(env.VITE_PASSWORD_MIN_LENGTH) || 8;
export const PASSWORD_BLOCK_COMMON = String(env.VITE_PASSWORD_BLOCK_COMMON).toLowerCase() === "true";
