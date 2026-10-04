import axios from "axios";

// One request per URL while it is in flight: the same list asked for by several loaders
// on one page (Policy Holder Information alone wanted /policyholders 6 times), or twice
// by React StrictMode in dev, shares a single response. A finished request is forgotten,
// so a later load (after an upload, a delete, a Needs Review resolve) always refetches.
const inFlight = new Map();

// Any write starts over, so no GET sent before an upload/delete/resolve is reused after it.
axios.interceptors.request.use((config) => {
  if ((config.method || "get").toLowerCase() !== "get") inFlight.clear();
  return config;
});

export function sharedGet(url, config = {}) {
  const key = `${url}?${new URLSearchParams(config.params || {})}`;
  if (!inFlight.has(key)) {
    const request = axios.get(url, config).finally(() => {
      if (inFlight.get(key) === request) inFlight.delete(key);
    });
    inFlight.set(key, request);
  }
  return inFlight.get(key);
}
