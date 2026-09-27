import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend, LabelList,
} from "recharts";
import { ChevronDown, Search } from "lucide-react";
import Sidebar from "../components/sidebar";
import FloodRiskModal from "../components/FloodRiskModal";
import { MonthYearPicker } from "../components/DatePicker";
import { fetchAllQuotations } from "../lib/quotations";

const API_BASE_URL = "http://127.0.0.1:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const PERIOD_TO_MONTHS = { "Past 6 Months": 6, "Past 3 Months": 3, "Past 12 Months": 12 };

const PIE_COLORS = ["#a5b4fc", "#6366f1"]; // [Not Yet Converted, Converted Account] — matches backend fire_pie/motor_pie order

// March Policy Forecast — genuinely depends on the not-yet-started
// predictive model (Objective 1.2), stays mock per explicit scope decision.
const forecastData = [{ name: "March", converted: 4, forecast: 10 }];

const PAGE_SIZE = 5;

function Dropdown({ label, options, value, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => !disabled && setOpen(o => !o)} disabled={disabled}
        title={disabled ? "Overridden by the selected month below" : undefined}
        className={`flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium transition whitespace-nowrap ${disabled ? "text-gray-300 cursor-not-allowed" : "text-gray-700 hover:border-gray-400"}`}>
        {value || label} <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && !disabled && options && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[140px]">
          {options.map(opt => (
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

function StatCard({ sub, value, label }) {
  return (
    <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">{sub}</p>
      <p className="text-black font-black text-5xl leading-none my-2">{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}

function MiniPie({ title, data, sub }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <p className="text-gray-400 text-[10px] mb-0.5">{sub}</p>
      <p className="font-bold text-black text-sm mb-2">{title}</p>
      <div className="flex items-center gap-3">
        <ResponsiveContainer width={110} height={95}>
          <PieChart>
            <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={44} labelLine={false}
              label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                const RADIAN = Math.PI / 180;
                const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                  fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={700}>{value}</text>;
              }}>
              {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-col gap-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i] }} />
              <span className="text-[10px] text-gray-600 leading-tight">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const RoundedBar = ({ x, y, width, height, fill }) => {
  const r = 5;
  if (!height || height <= 0) return null;
  return <path d={`M${x},${y+r} Q${x},${y} ${x+r},${y} L${x+width-r},${y} Q${x+width},${y} ${x+width},${y+r} L${x+width},${y+height} L${x},${y+height} Z`} fill={fill} />;
};
const BarValueLabel = ({ x, y, width, value }) => (
  <text x={x + width / 2} y={y + 18} fill="#fff" textAnchor="middle" fontSize={12} fontWeight={700}>{value}</text>
);

function formatQuoteDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d)) return "—";
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  return `${mm}/${dd}/${yyyy}`;
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function QuotationsProposal() {
  const [page, setPage]           = useState(1);
  const [period, setPeriod]       = useState("Past 6 Months");
  const [riskFilter, setRisk]     = useState("Risk Assessment: All");
  const [lineFilter, setLine]     = useState("Policy Line: All");
  const [statusFilter, setStatus] = useState("Status: All");
  const [month, setMonth]         = useState(null);
  const [search, setSearch]       = useState("");
  const [floodModalQuotation, setFloodModalQuotation] = useState(null);

  const [stats, setStats]         = useState(null);
  const [statsError, setStatsError] = useState(null);

  const [quotations, setQuotations]   = useState([]);
  const [quotationsLoading, setQuotationsLoading] = useState(true);
  const [quotationsError, setQuotationsError]     = useState(null);

  const fetchStats = useCallback(async (params) => {
    setStatsError(null);
    try {
      const res = await axios.get(`${API_BASE_URL}/stats/quotation-proposal`, {
        params,
        headers: authHeaders(),
      });
      setStats(res.data);
    } catch (err) {
      setStatsError("Failed to load quotation stats.");
    }
  }, []);

  // `month` (the calendar-month picker, cleared via "Show All Months")
  // takes over from `period` (the Past X Months dropdown) whenever it's
  // set — the dropdown is visually disabled in that state (see the
  // Dropdown below) rather than removed, since the user can always clear
  // the month to go back to it.
  useEffect(() => {
    if (month) {
      fetchStats({ year: month.getFullYear(), month: month.getMonth() + 1 });
    } else {
      fetchStats({ months: PERIOD_TO_MONTHS[period] ?? 6 });
    }
  }, [period, month, fetchStats]);

  useEffect(() => {
    (async () => {
      setQuotationsLoading(true);
      setQuotationsError(null);
      try {
        setQuotations(await fetchAllQuotations());
      } catch (err) {
        setQuotationsError("Failed to load quotations.");
      } finally {
        setQuotationsLoading(false);
      }
    })();
  }, []);

  // The bar's full height must equal the real total (t.quotation_count),
  // with "Converted" as a segment WITHIN it — not stacked on top of it.
  // Stacking converted_count + quotation_count (the raw total) double-
  // counts, since quotation_count already includes the converted ones;
  // stack converted_count + (total - converted) instead, so the two
  // segments sum exactly to the total.
  const trendData = (stats?.trend ?? []).map((t) => ({
    label: t.label,
    converted_count: t.converted_count,
    not_converted_count: Math.max(0, t.quotation_count - t.converted_count),
  }));

  // Table rows are scoped to the exact same range_start/range_end the
  // backend used for the KPI cards/pies/trend above (rolling window OR the
  // one selected month) — reuses the backend's own date math instead of
  // re-deriving "Past X Months" bounds in JS. Both are plain ISO
  // "YYYY-MM-DD" strings, so a lexicographic compare is a valid date
  // compare. A quotation with no date is excluded either way, same as the
  // backend's own SQL range filter excludes NULL quotation_date rows.
  const filtered = quotations.filter((q) => {
    const matchRange = !!stats && !!q.quotation_date
      && q.quotation_date >= stats.range_start && q.quotation_date <= stats.range_end;
    const matchLine = lineFilter === "Policy Line: All" || q.line === lineFilter;
    // Risk Assessment is still a fixed "Pending" placeholder (see the table
    // cell below) — its filter can only ever match "Pending" or "All", never
    // a specific outcome, since there's no real value yet.
    const matchRisk = riskFilter === "Risk Assessment: All" || riskFilter === "Pending";
    // Status is real, unlike Risk Assessment above — same "has a linked
    // policy" definition the "Converted Accounts" KPI card already uses
    // (q.is_converted comes straight from fetchAllQuotations() in
    // lib/quotations.js).
    const matchStatus = statusFilter === "Status: All"
      || (statusFilter === "Converted" && q.is_converted)
      || (statusFilter === "Not Yet Converted" && !q.is_converted);
    // Same substring-across-all-fields pattern as Policy Holder Info's
    // Quotation tab search (policy.jsx) -- not restricted to Client Name/
    // Quote Number, matches whatever the existing convention already does.
    const searchText = search.toLowerCase();
    const matchSearch = searchText === "" || Object.values(q).some((v) =>
      String(v).toLowerCase().includes(searchText)
    );
    return matchRange && matchLine && matchRisk && matchStatus && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const pageRows   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };

  const conversionRateLabel = stats ? `${Math.round(stats.conversion_rate)}%` : "—";

  // Drives the "All time" replacement sub-label on the 3 KPI cards + both
  // pies — reflects whichever filter is actually active.
  const periodLabel = month
    ? `${MONTH_NAMES[month.getMonth()]} ${month.getFullYear()}`
    : period;

  const currentYear = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0"><Sidebar activeItem="Quotations/ Proposal" /></div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        <div className="grid grid-cols-3 gap-4">
          <StatCard sub={periodLabel} value={stats ? stats.total_quotations : "—"} label="Total Quotations" />
          <StatCard sub={periodLabel} value={stats ? stats.converted_accounts : "—"} label="Converted Accounts" />
          <StatCard sub={periodLabel} value={conversionRateLabel} label="Conversion Rate" />
        </div>
        {statsError && <p className="text-xs text-red-600 bg-white/70 rounded-lg px-3 py-2">{statsError}</p>}

        <div className="flex gap-4">
          <div className="flex-1 bg-white rounded-2xl p-5 shadow-sm flex flex-col gap-3 min-w-0">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-black text-sm">
                {month ? "Daily Quotation Conversion Trend" : "Monthly Quotation Conversion Trend"}
              </h2>
              <Dropdown
                label="Past 6 Months"
                options={["Past 6 Months", "Past 3 Months", "Past 12 Months"]}
                value={period}
                onChange={setPeriod}
                disabled={!!month}
              />
            </div>
            <ResponsiveContainer width="100%" height={270}>
              <BarChart data={trendData} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false}
                  label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {/* Explicit LabelList per segment: a stacked Bar's built-in label shows the
                    running total on the upper segment, not its own count. */}
                <Bar dataKey="converted_count" name="Converted" stackId="a" fill="#6366f1">
                  <LabelList dataKey="converted_count" position="center" formatter={(v) => v || ""}
                    style={{ fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                </Bar>
                <Bar dataKey="not_converted_count" name="Not Yet Converted" stackId="a" fill="#a5b4fc" radius={[4,4,0,0]}>
                  <LabelList dataKey="not_converted_count" position="center" formatter={(v) => v || ""}
                    style={{ fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <MiniPie title="Fire & Property" data={stats?.fire_pie ?? []} sub={periodLabel} />
            <MiniPie title="Motor & Car"     data={stats?.motor_pie ?? []} sub={periodLabel} />
          </div>
        </div>

        <div className="flex gap-4">
          <div className="bg-white rounded-2xl p-5 shadow-sm min-w-0 flex flex-col flex-1">
            <div className="flex flex-wrap gap-2 mb-4 items-center">
              <div className="flex items-center gap-2">
                {month && (
                  <button
                    type="button"
                    onClick={() => handleFilterChange(setMonth)(null)}
                    className="flex items-center cursor-pointer gap-1.5 bg-violet-50 border border-violet-200 text-violet-600 text-xs font-semibold px-3 py-1.5 rounded-xl hover:bg-violet-50 hover:border-violet-200 hover:text-violet-500 transition"
                  >
                    Show All Months
                  </button>
                )}
                <MonthYearPicker value={month} onChange={handleFilterChange(setMonth)} />
              </div>
              <Dropdown label="Risk Assessment: All" options={["Risk Assessment: All","Pending"]} value={riskFilter} onChange={handleFilterChange(setRisk)} />
              <Dropdown label="Policy Line: All"     options={["Policy Line: All","Fire & Property","Motor Car"]} value={lineFilter} onChange={handleFilterChange(setLine)} />
              <Dropdown label="Status: All"          options={["Status: All","Converted","Not Yet Converted"]} value={statusFilter} onChange={handleFilterChange(setStatus)} />
              <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
                <Search className="w-3.5 h-3.5 text-gray-400" />
                <input className="text-xs outline-none text-gray-600 w-36"
                  placeholder="Search Quotation..."
                  value={search}
                  onChange={(e) => handleFilterChange(setSearch)(e.target.value)} />
              </div>
              {search && (
                <span className="text-xs text-gray-400">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>
              )}
            </div>
            {quotationsError && <p className="text-xs text-red-600 mb-3">{quotationsError}</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-center">
                <thead>
                  <tr className="border-b border-gray-100">
                    {["Quote Number","Client Name","Insurance Line","Quotation Date","Status","Risk Assessment","Claim Possibility","Geospatial Information"].map(h => (
                      <th key={h} className="py-2 px-2 text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {quotationsLoading && (
                    <tr><td colSpan={8} className="py-6 text-gray-400 text-xs">Loading quotations…</td></tr>
                  )}
                  {!quotationsLoading && pageRows.map((r) => (
                    <tr key={`${r.line}-${r.id}`} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="py-2.5 px-2">{r.id}</td>
                      <td className="py-2.5 px-2">{r.client_name || "—"}</td>
                      <td className="py-2.5 px-2">{r.line}</td>
                      <td className="py-2.5 px-2">{formatQuoteDate(r.quotation_date)}</td>
                      <td className="py-2.5 px-2">{r.is_converted ? (r.converted_policy_no || "Converted") : "Not Yet Converted"}</td>
                      {/* Risk Assessment / Claim Possibility: honest fixed
                          placeholder, not real data — same "not yet
                          computable" pattern as Overview's Filed Claims "—",
                          since both genuinely depend on the not-yet-started
                          predictive model (Objective 1.2). */}
                      <td className="py-2.5 px-2 text-gray-400">Pending</td>
                      <td className="py-2.5 px-2 text-gray-400">Pending</td>
                      <td className="py-2.5 px-2">
                        <button onClick={() => setFloodModalQuotation(r)}
                          className="bg-black text-white text-[11px] px-3 py-1 rounded-lg hover:bg-gray-800 transition">View</button>
                      </td>
                    </tr>
                  ))}
                  {!quotationsLoading && pageRows.length === 0 && (
                    <tr><td colSpan={8} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end items-center gap-2 mt-auto text-xs text-gray-500">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
              <span>{safePage} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
            </div>
          </div>

          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            {/* Still mock — depends on the not-yet-started predictive model
                (Objective 1.2). Yearly-scoped, deliberately independent of
                both the Past X Months and specific-month filters above. */}
            <div className="bg-white rounded-2xl p-5 shadow-sm flex flex-col gap-1">
              <p className="text-gray-400 text-[10px]">As of {currentYear}</p>
              <div className="flex items-center gap-3">
                <p className="text-black font-black text-4xl leading-none">50%</p>
                <p className="text-gray-600 text-xs leading-snug">Average Quotation<br />Claiming Rate</p>
              </div>
            </div>
            <div className="bg-white rounded-2xl p-5 shadow-sm flex-1">
              <p className="text-gray-400 text-[10px] text-center mb-1">As of {currentYear}</p>
              <h2 className="font-bold text-black text-sm mb-3 text-center">March Policy Forecast</h2>
              <ResponsiveContainer width="100%" height={170}>
                <BarChart data={forecastData} barGap={8} barCategoryGap="25%" margin={{ top:8, right:8, left:-20, bottom:0 }}>
                  <CartesianGrid vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} domain={[0,10]} ticks={[0,2,4,6,8,10]} />
                  <defs>
                    <linearGradient id="fcastGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#c4b5fd"/><stop offset="100%" stopColor="#818cf8"/>
                    </linearGradient>
                  </defs>
                  <Bar dataKey="converted" barSize={50} shape={(p) => <RoundedBar {...p} fill="#7c6ff7" />} label={<BarValueLabel />} />
                  <Bar dataKey="forecast"  barSize={50} shape={(p) => <RoundedBar {...p} fill="url(#fcastGrad)" />} label={<BarValueLabel />} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <FloodRiskModal
          isOpen={!!floodModalQuotation}
          onClose={() => setFloodModalQuotation(null)}
          quotation={floodModalQuotation}
        />
      </div>
    </div>
  );
}
