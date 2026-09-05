import { useState } from "react";
import axios from "axios";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { ChevronDown, Search } from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000";
const PAGE_SIZE = 8;

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// ── Date/format helpers ─────────────────────────────────────────────────────
export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatHumanDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return "";
  return `${MONTH_NAMES[m - 1]} ${d} ${y}`;
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

// Derived, not stored — a policy is "Renewed" if it carries a
// renewing_policy_no, "New" otherwise. Mirrors the backend's
// /stats/policy-distribution logic exactly.
export function deriveStatus(renewingPolicyNo) {
  return renewingPolicyNo && renewingPolicyNo.trim() ? "Renewed" : "New";
}

// { start, end } ISO bounds for a period, anchored on refDateISO — mirrors
// Backend/app/routers/stats.py's _range_for_period exactly, so the table
// below always agrees with the stat cards/charts above it.
export function getPeriodRange(period, refDateISO) {
  const [y, m] = refDateISO.split("-").map(Number);
  if (period === "daily") return { start: refDateISO, end: refDateISO };
  if (period === "mtd") return { start: `${y}-${String(m).padStart(2, "0")}-01`, end: refDateISO };
  return { start: `${y}-01-01`, end: refDateISO }; // ytd
}

export function filterRowsByRange(rows, start, end) {
  return rows.filter((r) => r.issuedRaw && r.issuedRaw >= start && r.issuedRaw <= end);
}

// ── Real policy data (Fire/Property + Motor/Car, combined) ─────────────────
// Same join as pages/policy.jsx's fetchFirePropertyPolicies/fetchMotorPolicies:
// policy → quotation → insurance_case → policyholder, to resolve the real
// Client Name. Returns rows already shaped for PolicyTable below.
export async function fetchDistributionPolicies() {
  const token = localStorage.getItem("token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const [firePolRes, fireQuoRes, motorPolRes, motorQuoRes, casesRes, phRes] = await Promise.all([
    axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
    axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
    axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
    axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
    axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
    axios.get(`${API_BASE_URL}/policyholders`, { headers }),
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
    sum: "—", // no sum-insured-equivalent field on MotorPolicy
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
export function StatCard({ sub, value, label }) {
  return (
    <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">{sub}</p>
      <p className="text-black font-black text-xl md:text-4xl leading-none my-2">{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}

// ── PolicyTable ───────────────────────────────────────────────────────────────
export function PolicyTable({
  search, setSearch, extraFilters, data,
  statusOptions = ["Status: All", "New", "Renewed"],
  premiumLabel = "Total Amount Due",
}) {
  const [page, setPage] = useState(1);
  const [lineFilter, setLine] = useState("Policy Line: All");
  const [statusFilter, setStatus] = useState("Status: All");
  const [expirySort, setExpirySort] = useState(null); // null | "asc" | "desc"

  let filtered = (data ?? []).filter((r) => {
    const matchLine = lineFilter === "Policy Line: All" || r.line === lineFilter;
    const matchStatus = statusFilter === "Status: All" || r.status === statusFilter;
    const matchSearch =
      r.policy.toLowerCase().includes(search.toLowerCase()) ||
      r.client.toLowerCase().includes(search.toLowerCase());
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
export function MiniPie({ title, data, colors, sub }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="font-bold text-black text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">{sub}</p>
      </div>
      <div className="flex items-center gap-3">
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
        <div className="flex flex-col gap-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: colors[i] }} />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
