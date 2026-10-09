import axios from "axios";
import { API_BASE_URL } from "./config";
import { clearSession } from "../lib/session";
import { SESSION_EXPIRED_KEY, reasonFor401 } from "../lib/logoutReason";

export { SESSION_EXPIRED_KEY };
let redirecting = false;

// Any 401 (expired or invalid login) from any request except the login itself: clear the login
// and go to the Login page, which then shows "Your session has expired" (or, when the password
// was changed on another device, "Your password was changed"). Installed on plain
// axios (used by most pages) and on the `api` instance below, so no page needs its own handling.
// Imported once in main.jsx so it is in place before any page makes a request.
function handleUnauthorized(error) {
  const url = error.config?.url || "";
  if (error.response?.status === 401 && !url.endsWith("/login") && !redirecting) {
    redirecting = true;
    clearSession();
    sessionStorage.setItem(SESSION_EXPIRED_KEY, reasonFor401(error.response.data?.detail));
    window.location.href = "/";
  }
  return Promise.reject(error);
}

axios.interceptors.response.use((response) => response, handleUnauthorized);

const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use((response) => response, handleUnauthorized);

export default api;
