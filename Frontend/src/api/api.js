import axios from "axios";

export const SESSION_EXPIRED_KEY = "sessionExpired";
let redirecting = false;

// Any 401 (expired or invalid login) from any request except the login itself: clear the login
// and go to the Login page, which then shows "Your session has expired". Installed on plain
// axios (used by most pages) and on the `api` instance below, so no page needs its own handling.
// Imported once in main.jsx so it is in place before any page makes a request.
function handleUnauthorized(error) {
  const url = error.config?.url || "";
  if (error.response?.status === 401 && !url.endsWith("/login") && !redirecting) {
    redirecting = true;
    localStorage.clear();
    sessionStorage.setItem(SESSION_EXPIRED_KEY, "1");
    window.location.href = "/";
  }
  return Promise.reject(error);
}

axios.interceptors.response.use((response) => response, handleUnauthorized);

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
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
