import { formatDateSlash, formatCurrencyPH } from "./PolicyDistributionShared";
import { FullCalendarPicker } from "./DatePicker";

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

export function RenewalRateCard({ rate, sub }) {
  return (
    <div className="w-64 h-fit flex-shrink-0 bg-white rounded-2xl p-5 shadow-sm flex flex-col justify-center">
      <p className="text-black font-bold text-sm">Renewal Rate</p>
      <p className="text-gray-400 text-[10px] mt-0.5">{sub}</p>
      <p className="text-black font-black text-5xl mt-3">{rate}</p>
      <p className="text-gray-400 text-[10px] mt-2">Renewal Rate = Renewed ÷ Expiring × 100</p>
    </div>
  );
}
