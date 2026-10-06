import { useState, useEffect } from "react";
import { sharedGet } from "../lib/sharedGet";
import { formatDateSlash, formatCurrencyPH, todayISO } from "./PolicyDistributionShared";
import { FullCalendarPicker, MonthYearPicker, MTDMonthPicker } from "./DatePicker";

import { API_BASE_URL } from "../api/config";

// Same 3 slices on every pie/bar in this feature (Renewed/Lost/Pending) —
// unlike Distribution's fire/motor pies, which use different color pairs
// per line, Renewal's line pies share one palette since the slice meaning
// (status) is identical across lines.
export const RENEWAL_PIE_COLORS = ["#6366f1", "#f87171", "#d1d5db"];

export const RENEWAL_STATUS_OPTIONS = ["Status: All", "Renewed", "Lost", "Pending"];

// Backend's RenewalPolicyRow -> PolicyTable's expected row shape (same
// shape Distribution's fetchDistributionPolicies produces), so the
// existing PolicyTable component can render it unchanged.
export function mapRenewalRow(p) {
  const linePrefix = p.line === "Fire & Property" ? "fire" : "motor";
  return {
    key: `${linePrefix}-${p.id}`,
    policy: p.policy_no || `#${p.id}`,
    client: p.client_name || "—",
    line: p.line,
    issued: formatDateSlash(p.issue_date),
    expiryRaw: p.expiry_date,
    expiry: formatDateSlash(p.expiry_date),
    premium: formatCurrencyPH(p.total_amount_due),
    sum: p.sum_insured != null ? formatCurrencyPH(p.sum_insured) : "—",
    status: p.status,
  };
}

// ── Expiry date calendar filter ──────────────────────────────────────────
// Pure client-side table filter, same pattern as policy.jsx's month/year
// filter: narrows the already-fetched `policies` rows by expiry date only.
// Deliberately NOT wired to the /stats/renewal-ratio `date` query param —
// that param is "today" for the Lost/Pending math and the mtd/ytd window,
// and must stay fixed to the real current date regardless of what the user
// picks here. Only FullCalendarPicker (the UI control) is reused; none of
// its callers' API-param-passing wiring comes with it.
function toLocalISO(date) {
  if (!date) return null;
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function filterRowsByExpiryDate(rows, pickedDate) {
  if (!pickedDate) return rows;
  const iso = toLocalISO(pickedDate);
  return rows.filter((r) => r.expiryRaw === iso);
}

export function ExpiryDateFilter({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <FullCalendarPicker value={value} onChange={onChange} />
      {value && (
        <button onClick={() => onChange(null)} className="text-[10px] text-gray-400 hover:text-gray-600 underline">
          Clear
        </button>
      )}
    </div>
  );
}

// ── Expiry MONTH filter (YTD only) ────────────────────────────────────────
// Same pure client-side pattern as filterRowsByExpiryDate/ExpiryDateFilter
// above, but narrows by calendar month instead of an exact day — YTD's
// table has too many days in view for a single-day filter to be useful.
// Daily/MTD keep the exact-day filter unchanged; this is YTD-only.
export function filterRowsByExpiryMonth(rows, pickedMonth) {
  if (!pickedMonth) return rows;
  const d = new Date(pickedMonth);
  const year = d.getFullYear();
  const month = d.getMonth();
  return rows.filter((r) => {
    if (!r.expiryRaw) return false;
    const [ry, rm] = r.expiryRaw.split("-").map(Number);
    return ry === year && rm === month + 1;
  });
}

export function MonthExpiryFilter({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <MonthYearPicker value={value} onChange={onChange} />
      {value && (
        <button onClick={() => onChange(null)} className="text-[10px] text-gray-400 hover:text-gray-600 underline">
          Clear
        </button>
      )}
    </div>
  );
}

// ── Expiry MONTH filter (MTD only) ────────────────────────────────────────
// Same pure client-side pattern as MonthExpiryFilter above (reuses the same
// filterRowsByExpiryMonth), but the picker itself is restricted to
// January..current month (MTDMonthPicker) instead of MonthYearPicker's free
// multi-year scroll -- MTD's table should never offer a future month.
export function MonthExpiryFilterMTD({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <MTDMonthPicker value={value} onChange={onChange} />
      {value && (
        <button onClick={() => onChange(null)} className="text-[10px] text-gray-400 hover:text-gray-600 underline">
          Clear
        </button>
      )}
    </div>
  );
}

// ── Shared YTD renewal rate ──────────────────────────────────────────────
// The Renewal Rate card always shows the YTD figure regardless of which
// period tab (Daily/MTD/YTD) is active -- fetched ONCE here at the page
// level (renewal.jsx) and handed down to all 3 views, rather than each
// view fetching its own copy on every tab switch. Every other stat card/
// chart/table on each view is untouched and still scoped to that view's
// own period.
export function useYtdRenewalRate() {
  const [rate, setRate] = useState(null); // null = still loading

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const token = localStorage.getItem("token");
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await sharedGet(`${API_BASE_URL}/stats/renewal-ratio`, {
          headers,
          params: { period: "ytd", date: todayISO() },
        });
        if (!cancelled) setRate(res.data.renewal_rate);
      } catch {
        if (!cancelled) setRate(null);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return rate;
}

export function RenewalRateCard({ rate }) {
  return (
    <div className="w-64 h-fit flex-shrink-0 bg-white rounded-2xl p-5 shadow-sm flex flex-col justify-center">
      <p className="text-black font-bold text-sm">Current Renewal Rate (YTD)</p>
      <p className="text-black font-black text-5xl mt-3">{rate}</p>
      <p className="text-gray-400 text-[10px] mt-2">Renewal Rate = Renewed ÷ (Renewed + Lost) × 100 · Pending excluded</p>
    </div>
  );
}
