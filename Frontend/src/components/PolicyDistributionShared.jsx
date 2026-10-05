import { useState } from "react";
import { sharedGet } from "../lib/sharedGet";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { ChevronDown, Search } from "lucide-react";
import { fieldsMatchSearch } from "../lib/search";

const API_BASE_URL = "http://127.0.0.1:8000";
const PAGE_SIZE = 8;

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// ── Date/format helpers ─────────────────────────────────────────────────────
export function dateToISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function todayISO() {
  return dateToISO(new Date());
}

export function formatHumanDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return "";
  return `${MONTH_NAMES[m - 1]} ${d} ${y}`;
}

// Month-Year and Year-only variants of formatHumanDate, for MTD/YTD stat
// card captions — a "day" is meaningless once the view represents a whole
// month or year, so those periods must drop it rather than reuse the
// Daily-granularity full date.
export function formatMonthYear(iso) {
  if (!iso) return "";
  const [y, m] = iso.split("-").map(Number);
  if (!y || !m) return "";
  return `${MONTH_NAMES[m - 1]} ${y}`;
}

export function formatYearOnly(iso) {
  if (!iso) return "";
  const [y] = iso.split("-").map(Number);
  if (!y) return "";
  return `${y}`;
}

export function formatDateSlash(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return "—";
  return `${String(m).padStart(2, "0")}/${String(d).padStart(2, "0")}/${y}`;
}

// dashIfEmpty=false is for aggregate totals (always a real number, even
// zero) — dashIfEmpty=true (default) is for a single policy's own field,
// where blank means the data just isn't on file (same convention as
// policy.jsx's formatCurrency).
export function formatCurrencyPH(value, dashIfEmpty = true) {
  if (value === null || value === undefined || value === "") {
    return dashIfEmpty ? "—" : "₱0.00";
  }
  const n = Number(value);
  if (isNaN(n)) return dashIfEmpty ? "—" : "₱0.00";
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Derived, not stored — a policy is a "Renewal" (it itself renews an earlier
// policy) if it carries a renewing_policy_no, "New" otherwise. Mirrors the
// backend's /stats/policy-distribution logic exactly. Deliberately not
// "Renewed": on Renewal Ratio, "Renewed" means ANOTHER policy renews this one.
export function deriveStatus(renewingPolicyNo) {
  return renewingPolicyNo && renewingPolicyNo.trim() ? "Renewal" : "New";
}

// { start, end } ISO bounds for a period, anchored on refDateISO — mirrors
// Backend/app/routers/stats.py's _range_for_period exactly, so the table
// below always agrees with the stat cards/charts above it.
export function getPeriodRange(period, refDateISO) {
  const [y, m] = refDateISO.split("-").map(Number);
  if (period === "daily") return { start: refDateISO, end: refDateISO };
  if (period === "mtd") {
    const start = `${y}-${String(m).padStart(2, "0")}-01`;
    const todayIso = todayISO();
    const [ty, tm] = todayIso.split("-").map(Number);
    // Mirrors Backend/app/routers/stats.py's _range_for_period exactly:
    // the current month is cut off at today (never show days that
    // haven't happened yet); any other (i.e. past) picked month gets its
    // full range, nothing left to cut off.
    if (y === ty && m === tm) return { start, end: todayIso };
    const lastDay = new Date(y, m, 0).getDate();
    return { start, end: `${y}-${String(m).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}` };
  }
  return { start: `${y}-01-01`, end: refDateISO }; // ytd
}

export function filterRowsByRange(rows, start, end) {
  return rows.filter((r) => r.issuedRaw && r.issuedRaw >= start && r.issuedRaw <= end);
}

// Pure client-side table filter, same pattern as RenewalRatioShared's
// filterRowsByExpiryMonth — narrows to rows issued within exactly the
// picked calendar month. Deliberately NOT cumulative (Jan-through-month):
// picking "August" must mean "just August", not "January through August"
// (the previous endOfMonthISO-driven cutoff read confusingly and also
// leaked into the stat cards/pie/bar via the backend `date` param).
export function filterRowsByIssuedMonth(rows, pickedMonth) {
  if (!pickedMonth) return rows;
  const d = new Date(pickedMonth);
  const year = d.getFullYear();
  const month = d.getMonth();
  return rows.filter((r) => {
    if (!r.issuedRaw) return false;
    const [ry, rm] = r.issuedRaw.split("-").map(Number);
    return ry === year && rm === month + 1;
  });
}

// ── Real policy data (Fire/Property + Motor/Car, combined) ─────────────────
// Same join as pages/policy.jsx's fetchFirePropertyPolicies/fetchMotorPolicies:
// policy → quotation → insurance_case → policyholder, to resolve the real
// Client Name. Returns rows already shaped for PolicyTable below.
export async function fetchDistributionPolicies() {
  const token = localStorage.getItem("token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const [firePolRes, fireQuoRes, motorPolRes, motorQuoRes, casesRes, phRes] = await Promise.all([
    sharedGet(`${API_BASE_URL}/fire-property/policies`, { headers }),
    sharedGet(`${API_BASE_URL}/fire-property/quotations`, { headers }),
    sharedGet(`${API_BASE_URL}/motor/policies`, { headers }),
    sharedGet(`${API_BASE_URL}/motor/quotations`, { headers }),
    sharedGet(`${API_BASE_URL}/insurance-cases`, { headers }),
    sharedGet(`${API_BASE_URL}/policyholders`, { headers }),
  ]);

  const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
  const nameByPolicyholder = new Map(
    phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
  );
  const fireCaseByQuotation = new Map(fireQuoRes.data.map((q) => [q.id, q.insurance_case_id]));
  const motorCaseByQuotation = new Map(motorQuoRes.data.map((q) => [q.id, q.insurance_case_id]));

  function clientNameFor(caseByQuotation, quotationId) {
    const caseId = caseByQuotation.get(quotationId);
    const policyholderId = caseId !== undefined ? policyholderByCase.get(caseId) : undefined;
    return nameByPolicyholder.get(policyholderId) || "—";
  }

  const fireRows = firePolRes.data.map((p) => ({
    key: `fire-${p.id}`,
    policy: p.policy_no || `#${p.id}`,
    client: clientNameFor(fireCaseByQuotation, p.quotation_id),
    line: "Fire & Property",
    issuedRaw: p.issue_date,
    issued: formatDateSlash(p.issue_date),
    expiryRaw: p.period_to,
    expiry: formatDateSlash(p.period_to),
    premium: formatCurrencyPH(p.total_amount_due),
    sum: formatCurrencyPH(p.sum_insured),
    status: deriveStatus(p.renewing_policy_no),
  }));

  const motorRows = motorPolRes.data.map((p) => ({
    key: `motor-${p.id}`,
    policy: p.policy_no || `#${p.id}`,
    client: clientNameFor(motorCaseByQuotation, p.quotation_id),
    line: "Motor Car",
    issuedRaw: p.issue_date,
    issued: formatDateSlash(p.issue_date),
    expiryRaw: p.period_to,
    expiry: formatDateSlash(p.period_to),
    premium: formatCurrencyPH(p.total_amount_due),
    sum: formatCurrencyPH(p.sum_insured),
    status: deriveStatus(p.renewing_policy_no),
  }));

  return [...fireRows, ...motorRows];
}

// ── Dropdown ──────────────────────────────────────────────────────────────────
export function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
        {value || label}
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && options && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[140px]">
          {options.map((opt) => (
            <button key={opt} onClick={() => { onChange?.(opt); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${(value || label) === opt ? "font-bold text-black" : "text-gray-600"}`}>
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── StatCard ──────────────────────────────────────────────────────────────────
// `note` (optional) is a small caption under the label, e.g. what the card counts.
// A long value (a ₱ amount in the millions) shrinks to fit the card instead of spilling
// past it: the card is a size container, and the font is the usual size or, if the value
// is too long for it, the card's width (cqw) divided by its length (~0.6em per character).
export function StatCard({ sub, value, label, note }) {
  const fitWidth = `${(100 / (0.6 * Math.max(String(value).length, 1))).toFixed(1)}cqw`;
  return (
    <div className="@container bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">{sub}</p>
      <p className="text-black font-black leading-none my-2 whitespace-nowrap [--stat-max:1.25rem] md:[--stat-max:2.25rem]"
        style={{ fontSize: `min(var(--stat-max), ${fitWidth})` }}>{value}</p>
      <div>
        <p className="text-gray-500 text-xs">{label}</p>
        {note && <p className="text-gray-400 text-[10px] leading-snug">{note}</p>}
      </div>
    </div>
  );
}

// ── PolicyTable ───────────────────────────────────────────────────────────────
export function PolicyTable({
  search, setSearch, extraFilters, data,
  statusOptions = ["Status: All", "New", "Renewal"],
  premiumLabel = "Total Amount Due",
}) {
  const [page, setPage] = useState(1);
  const [lineFilter, setLine] = useState("Policy Line: All");
  const [statusFilter, setStatus] = useState("Status: All");
  const [expirySort, setExpirySort] = useState(null); // null | "asc" | "desc"

  let filtered = (data ?? []).filter((r) => {
    const matchLine = lineFilter === "Policy Line: All" || r.line === lineFilter;
    const matchStatus = statusFilter === "Status: All" || r.status === statusFilter;
    // Every typed word must appear in the policy number or the client (lib/search.js).
    const matchSearch = fieldsMatchSearch([r.policy, r.client], search);
    return matchLine && matchStatus && matchSearch;
  });

  if (expirySort) {
    // Sort on the raw ISO expiry date, not the display string (a MM/DD/YYYY
    // string sorts lexicographically wrong). Rows with no expiry on file
    // always sink to the bottom regardless of direction.
    const withExpiry = filtered.filter((r) => r.expiryRaw);
    const withoutExpiry = filtered.filter((r) => !r.expiryRaw);
    withExpiry.sort((a, b) =>
      expirySort === "asc" ? a.expiryRaw.localeCompare(b.expiryRaw) : b.expiryRaw.localeCompare(a.expiryRaw)
    );
    filtered = [...withExpiry, ...withoutExpiry];
  }

  const toggleExpirySort = () => {
    setExpirySort((d) => (d === null ? "asc" : d === "asc" ? "desc" : null));
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleLineChange = (val) => { setLine(val); setPage(1); };
  const handleStatusChange = (val) => { setStatus(val); setPage(1); };
  const handleSearch = (e) => { setSearch(e.target.value); setPage(1); };

  return (
    <div className="bg-white min-h-[500px] rounded-2xl p-5 shadow-sm flex flex-col flex-1">
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Dropdown label="Policy Line: All" options={["Policy Line: All", "Motor Car", "Fire & Property"]} value={lineFilter} onChange={handleLineChange} />
        <Dropdown label="Status: All" options={statusOptions} value={statusFilter} onChange={handleStatusChange} />
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
          <Search className="w-3.5 h-3.5 text-gray-400" />
          <input className="text-xs outline-none text-gray-600 w-36" placeholder="Search Policy Number" value={search} onChange={handleSearch} />
        </div>
        {extraFilters}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs text-center">
          <thead>
            <tr className="border-b border-gray-200">
              {["Policy Number", "Client Name", "Policy Line", "Issued Date", "Expiry Date", premiumLabel, "Sum Insured", "Status"].map((h) =>
                h === "Expiry Date" ? (
                  <th key={h} onClick={toggleExpirySort} title="Sort by expiry date"
                    className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap cursor-pointer select-none hover:text-black transition">
                    Expiry Date {expirySort === "asc" ? "▲" : expirySort === "desc" ? "▼" : ""}
                  </th>
                ) : (
                  <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr key={r.key} className="border-b border-gray-50 hover:bg-gray-50 transition">
                <td className="py-3 px-3">{r.policy}</td>
                <td className="py-3 px-3">{r.client}</td>
                <td className="py-3 px-3">{r.line}</td>
                <td className="py-3 px-3">{r.issued}</td>
                <td className="py-3 px-3">{r.expiry}</td>
                <td className="py-3 px-3">{r.premium}</td>
                <td className="py-3 px-3">{r.sum}</td>
                <td className="py-3 px-3">{r.status}</td>
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr><td colSpan={8} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end items-center gap-2 mt-auto text-xs text-gray-500">
        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
        <span>{safePage} / {totalPages}</span>
        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
      </div>
    </div>
  );
}

// ── MiniPie ───────────────────────────────────────────────────────────────────
// `note` (optional) is a small caption under the chart -- e.g. what's excluded.
export function MiniPie({ title, data, colors, sub, note }) {
  // All-zero total (e.g. zero quotations this month): Recharts can't
  // compute slice angles from an all-zero pie and draws nothing, leaving a
  // blank gap. Swap in a neutral placeholder circle sized to match the real
  // chart, in the SAME flex slot, so the legend next to it never shifts
  // from its normal position.
  const total = data.reduce((sum, d) => sum + (d.value || 0), 0);

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <p className="font-bold text-black text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">{sub}</p>
      </div>
      {/* flex-1 + items-center: on pages where this card sits next to a
          taller sibling in a CSS grid row (e.g. Overview's bar chart), the
          card's outer box stretches to match — without this, the chart/
          legend row stays pinned to the top of that taller box instead of
          centering in it. Harmless where nothing stretches the card (e.g.
          Distribution/Renewal's stacked MiniPie column): flex-1 just
          resolves to the row's natural height there. */}
      <div className="flex items-center gap-3 flex-1">
        {total === 0 ? (
          <div style={{ width: 110, height: 100 }} className="flex items-center justify-center flex-shrink-0">
            <svg width={92} height={92}>
              <circle cx={46} cy={46} r={46} fill="#e5e7eb" />
              <text x={46} y={46} textAnchor="middle" dominantBaseline="central" fontSize={9} fontWeight={700} fill="#9ca3af">
                No data yet
              </text>
            </svg>
          </div>
        ) : (
          <ResponsiveContainer width={110} height={100}>
            <PieChart>
              <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={46} labelLine={false}
                label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                  // A 0-value slice has no arc to anchor a label to — Recharts
                  // still calls this with a midAngle sitting on the boundary
                  // between its neighbors, so the "0" renders overlapping
                  // whichever slice edge is there. Suppress it; the category
                  // still shows in the legend below, just without a number.
                  if (!value) return null;
                  const RADIAN = Math.PI / 180;
                  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                  return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                    fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={700}>{value}</text>;
                }}>
                {data.map((_, i) => <Cell key={i} fill={colors[i]} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        )}
        <div className="flex flex-col gap-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: colors[i] }} />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
      {note && <p className="text-gray-400 text-[10px] mt-2">{note}</p>}
    </div>
  );
}
