import { sharedGet } from "./sharedGet";

import { API_BASE_URL } from "../api/config";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Model predictions and scores (backend app/ml/, GET /ml/...). Predictions are stored
// apart from the real data and exist only for rows that still need one: open or
// in-force quotations, and Paid Claims not yet investigated. Everything else shows "—".
// These helpers never throw -- a page must still load if the model endpoints fail,
// it just shows "—" / "Not trained yet".

export const RISK_LEVELS = ["Low", "Medium", "High"];

// "Motor Car-123" -> { claim_probability, risk_level }
export async function fetchQuotationPredictions() {
  try {
    const res = await sharedGet(`${API_BASE_URL}/ml/predictions/quotations`, { headers: authHeaders() });
    return new Map(res.data.map((p) => [`${p.line}-${p.quotation_id}`, p]));
  } catch {
    return new Map();
  }
}

// "Fire & Property-45" -> { fraud_probability, label }
export async function fetchClaimPredictions() {
  try {
    const res = await sharedGet(`${API_BASE_URL}/ml/predictions/claims`, { headers: authHeaders() });
    return new Map(res.data.map((p) => [`${p.line}-${p.claim_id}`, p]));
  } catch {
    return new Map();
  }
}

// What each model saw (GET /ml/inputs/..., read from the same frames as training).
// quotation_id -> schemas.MotorQuotationInputs | FireQuotationInputs, for ONE line.
export async function fetchQuotationInputs(line) {
  try {
    const res = await sharedGet(`${API_BASE_URL}/ml/inputs/quotations`, { params: { line }, headers: authHeaders() });
    return new Map(res.data.map((i) => [i.quotation_id, i]));
  } catch {
    return new Map();
  }
}

// "Motor Car-12" -> schemas.ClaimInputs (Paid Claims only; CNC Issuance rows have none).
export async function fetchClaimInputs() {
  try {
    const res = await sharedGet(`${API_BASE_URL}/ml/inputs/claims`, { headers: authHeaders() });
    return new Map(res.data.map((i) => [`${i.line}-${i.claim_id}`, i]));
  } catch {
    return new Map();
  }
}

// { byName: { motor_lr, fire_lr, fraud_nb } (schemas.MLModelSummary), refresh: { running, ... } }
export async function fetchModels() {
  try {
    const res = await sharedGet(`${API_BASE_URL}/ml/models`, { headers: authHeaders() });
    return { byName: Object.fromEntries(res.data.models.map((m) => [m.model_name, m])), refresh: res.data.refresh };
  } catch {
    return { byName: {}, refresh: null };
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// The backend retrains + rewrites predictions in the background a few seconds AFTER an
// upload/resolve response (app/ml/jobs.py). Poll GET /ml/models until that refresh is
// over, then the caller refetches. "Over" = it was seen running and has stopped; if it
// never shows up as running within startGraceMs (the upload had no learning data, or it
// already finished) we stop waiting too. A refresh takes at least ~5s, so the grace
// window can't miss one that is starting. Never throws; resolves to
// "finished" | "not_started" | "timeout" | "cancelled".
export async function waitForModelRefresh({
  intervalMs = 2000, startGraceMs = 4000, timeoutMs = 120000, isCancelled = () => false,
} = {}) {
  const start = Date.now();
  let sawRunning = false;
  while (!isCancelled()) {
    const { refresh } = await fetchModels();
    const running = !!refresh?.running;
    sawRunning = sawRunning || running;
    const elapsed = Date.now() - start;
    if (!running && sawRunning) return "finished";
    if (!running && elapsed >= startGraceMs) return "not_started";
    if (elapsed >= timeoutMs) return "timeout";
    await sleep(intervalMs);
  }
  return "cancelled";
}

export function formatPercent(value) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

// A prediction's probability next to its level: one decimal, rounded DOWN. The level
// thresholds are whole hundredths (Low/Medium/High from 0.21, 0.41 ...; fraud above 0.30,
// app/ml/training.py), so a value just under one never displays as reaching it
// (0.20985 -> "20.9%", where rounding would show "21.0%" next to a Medium "21.0%").
export function formatProbability(value) {
  if (value === null || value === undefined) return "—";
  return `${(Math.floor(value * 1000 + 1e-9) / 10).toFixed(1)}%`;
}

// Model accuracy cards: the same rounding as the report files (app/ml/report.py) —
// percentages with one decimal, AUC with three.
export function formatScorePercent(value) {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function formatTrainedDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? "—" : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
