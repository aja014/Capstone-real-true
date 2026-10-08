// Same limit as the backend (Backend/app/http_security.py): a bigger file is refused before it is sent.
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const FILE_TOO_LARGE = "File is too large (max 10 MB).";

export const isTooLarge = (file) => (file?.size ?? 0) > MAX_UPLOAD_BYTES;
