import { useState, useEffect, useCallback, useMemo, memo } from "react";
import { sharedGet } from "../lib/sharedGet";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend, LabelList,
} from "recharts";
import { ChevronDown, Search } from "lucide-react";
import Sidebar from "../components/sidebar";
import FloodRiskModal from "../components/FloodRiskModal";
import { MonthYearPicker } from "../components/DatePicker";
import { fetchAllQuotations } from "../lib/quotations";
import {
  fetchQuotationPredictions, fetchQuotationInputs, fetchModels, waitForModelRefresh, formatPercent, RISK_LEVELS,
} from "../lib/ml";
import { formatCurrencyPH } from "../components/PolicyDistributionShared";
import { RiskLevelCell, ClaimPossibilityCell, ModelAccuracyCard } from "../components/ModelShared";
import { rowMatchesSearch } from "../lib/search";

const API_BASE_URL = "http://127.0.0.1:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const PERIOD_TO_MONTHS = { "Past 6 Months": 6, "Past 3 Months": 3, "Past 12 Months": 12 };

const PIE_COLORS = ["#a5b4fc", "#6366f1"]; // [Not Yet Converted, Converted Account] — matches backend fire_pie/motor_pie order

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

// Memoized; callers pass `stats?.x_pie` as is (a `?? []` there would be a new array on every
// render and defeat the memo), so the empty fallback is this default instead.
const MiniPie = memo(function MiniPie({ title, data = [], sub }) {
  // All-zero data (e.g. a month with no quotations yet): the same grey "No data yet"
  // circle as the shared MiniPie, sized to this pie, so the legend doesn't move.
  const total = data.reduce((sum, d) => sum + (d.value || 0), 0);
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <p className="text-gray-400 text-[10px] mb-0.5">{sub}</p>
      <p className="font-bold text-black text-sm mb-2">{title}</p>
      <div className="flex items-center gap-3">
        {total === 0 ? (
          <div style={{ width: 110, height: 95 }} className="flex items-center justify-center flex-shrink-0">
            <svg width={88} height={88}>
              <circle cx={44} cy={44} r={44} fill="#e5e7eb" />
              <text x={44} y={44} textAnchor="middle" dominantBaseline="central" fontSize={9} fontWeight={700} fill="#9ca3af">
                No data yet
              </text>
            </svg>
          </div>
        ) : (
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
        )}
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
});

const LINES = ["Motor Car", "Fire & Property"];

// The table shows only what each Logistic Regression model uses (GET /ml/inputs/quotations,
// read from the same frames as training): [header, value as shown]. null -> "—".
const isMissing = (v) => v === null || v === undefined;
const yesNo = (v) => (isMissing(v) ? null : v ? "Yes" : "No");
const money = (v) => (isMissing(v) ? null : formatCurrencyPH(v));
const INPUT_COLUMNS = {
  "Motor Car": [
    ["Flood Risk Category", (i) => i.flood_category],
    ["Classification", (i) => i.classification],
    ["Make", (i) => i.make],
    ["Body Type", (i) => i.body_type],
    ["Color", (i) => i.color],
    ["Vehicle Age", (i) => (isMissing(i.vehicle_age) ? null : `${i.vehicle_age} yrs`)],
    ["Sum Insured", (i) => money(i.sum_insured)],
    ["Deductible", (i) => money(i.deductible)],
    ["Prior Claim", (i) => yesNo(i.prior_claim)],
  ],
  "Fire & Property": [
    ["Flood Risk Category", (i) => i.flood_category],
    ["Occupancy", (i) => i.occupancy],
    ["Overall Risk Assessment", (i) => i.overall_risk_assessment],
    ["Total Sum Insured", (i) => money(i.total_sum_insured)],
    ["Fire Protection Count", (i) => (isMissing(i.fire_protection_count) ? null : `${i.fire_protection_count} of 8`)],
    ["Construction Class B", (i) => yesNo(i.construction_class_b)],
    ["Loss Record", (i) => yesNo(i.has_loss_record)],
    ["Prior Claim", (i) => yesNo(i.prior_claim)],
  ],
};
// IDs first: Quote No. (the Quotation ID), the case, then the vehicle (Motor) or survey (Fire).
const ID_COLUMNS = {
  "Motor Car": [["Quote No.", (q) => q.quote_number], ["Case ID", (q) => q.insurance_case_id], ["Vehicle ID", (q) => q.vehicle_id]],
  "Fire & Property": [["Quote No.", (q) => q.quote_number], ["Case ID", (q) => q.insurance_case_id], ["Survey ID", (q) => q.survey_id]],
};

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Plain statistics from GET /stats/policy-forecast, not a model. Always both lines and
// never affected by the page's filters -- it is forward-looking, so it states its own basis.
function PolicyForecastCard({ forecast, error }) {
  const lineOf = (name) => forecast?.lines.find((l) => l.line === name);
  const motor = lineOf("Motor Car");
  const fire = lineOf("Fire & Property");
  const count = (n) => (n === null || n === undefined ? "—" : Math.round(n).toLocaleString());
  const rate = (r) => (r === null || r === undefined ? "—" : `${Math.round(r * 100)}%`);
  const policies = (n) => (n !== null && n !== undefined && Math.round(n) === 1 ? "policy" : "policies");
  const waitDays = forecast ? Math.max(...forecast.lines.map((l) => l.wait_days)) : null;
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm flex flex-col gap-1.5">
      <p className="text-black font-bold text-sm">
        {forecast ? `${MONTH_NAMES[forecast.target_month - 1]} Policy Forecast` : "Policy Forecast"}
      </p>
      {error ? (
        <p className="text-gray-400 text-xs">{error}</p>
      ) : !forecast ? (
        <p className="text-gray-400 text-xs">…</p>
      ) : (
        <>
          <p className="text-black text-xs">
            <span className="font-black text-4xl leading-none">≈ {count(forecast.expected_policies)}</span>
            <span className="text-gray-600"> new {policies(forecast.expected_policies)}</span>
          </p>
          <p className="text-gray-600 text-xs">
            Motor {count(motor?.expected_policies)} · Fire &amp; Property {count(fire?.expected_policies)}
          </p>
          <p className="text-gray-400 text-[10px] leading-snug">
            Based on ≈ {count(forecast.avg_quotations_per_month)} quotations a month and past conversion
            rates (Motor {rate(motor?.conversion_rate)} · Fire &amp; Property {rate(fire?.conversion_rate)}),
            past {forecast.history_months} months
          </p>
          <p className="text-gray-600 text-xs border-t border-gray-100 pt-1.5 mt-0.5">
            Open now: {forecast.open_quotations} quotation{forecast.open_quotations !== 1 ? "s" : ""} → ≈{" "}
            {count(forecast.expected_from_open)} {policies(forecast.expected_from_open)} within {waitDays} days
          </p>
          {forecast.backtest_error_pct !== null && (
            <p className="text-gray-400 text-[10px]">
              Backtest, last 12 months: off by {Math.round(forecast.backtest_error_pct)}% on average
            </p>
          )}
        </>
      )}
    </div>
  );
}

// The trend chart doesn't depend on the table's search/filters, so it is memoized and
// skips the page's re-render on every keystroke. Recharts 3 copies the axes', labels' and
// legend's props into its own store in effects; re-rendering it on each key of fast typing
// stacked those updates past React's limit ("Maximum update depth exceeded", blank page).
const TrendChart = memo(function TrendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <BarChart data={data} barCategoryGap="30%">
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
  );
});

export default function QuotationsProposal() {
  const [page, setPage]           = useState(1);
  const [period, setPeriod]       = useState("Past 6 Months");
  const [riskFilter, setRisk]     = useState("Risk Assessment: All");
  const [lineFilter, setLine]     = useState("Motor Car");
  const [statusFilter, setStatus] = useState("Status: All");
  const [month, setMonth]         = useState(null);
  const [search, setSearch]       = useState("");
  const [floodModalQuotation, setFloodModalQuotation] = useState(null);

  const [stats, setStats]         = useState(null);
  const [statsError, setStatsError] = useState(null);

  const [quotations, setQuotations]   = useState([]);
  const [quotationsLoading, setQuotationsLoading] = useState(true);
  const [quotationsError, setQuotationsError]     = useState(null);

  // Logistic Regression output (lib/ml.js): "line-id" -> { claim_probability, risk_level }.
  const [predictions, setPredictions] = useState(() => new Map());
  const [models, setModels] = useState(null); // GET /ml/models summaries; null while loading
  const [predictionsUpdating, setPredictionsUpdating] = useState(false);
  // Model inputs of the selected line: { line, byId: quotation_id -> inputs }. Kept with
  // its line because Motor and Fire quotation ids overlap.
  const [inputs, setInputs] = useState({ line: null, byId: new Map() });
  const [inputsVersion, setInputsVersion] = useState(0); // bumped after a background refresh

  const [forecast, setForecast] = useState(null);
  const [forecastError, setForecastError] = useState(null);

  const fetchStats = useCallback(async (params) => {
    setStatsError(null);
    try {
      const res = await sharedGet(`${API_BASE_URL}/stats/quotation-proposal`, {
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

  // Policy Forecast: fetched once, independent of every filter on this page.
  useEffect(() => {
    sharedGet(`${API_BASE_URL}/stats/policy-forecast`, { headers: authHeaders() })
      .then((res) => setForecast(res.data))
      .catch(() => setForecastError("Forecast not available."));
  }, []);

  // Predictions + model scores. If the page is opened while the background retrain
  // (started by an upload on Policy Holder Information) is still running, wait for it
  // and then show the fresh predictions and scores.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [preds, { byName, refresh }] = await Promise.all([fetchQuotationPredictions(), fetchModels()]);
      if (cancelled) return;
      setPredictions(preds);
      setModels(byName);
      if (!refresh?.running) return;
      setPredictionsUpdating(true);
      await waitForModelRefresh({ isCancelled: () => cancelled });
      if (cancelled) return;
      const [fresh, latest] = await Promise.all([fetchQuotationPredictions(), fetchModels()]);
      if (cancelled) return;
      setPredictions(fresh);
      setModels(latest.byName);
      setInputsVersion((v) => v + 1);
      setPredictionsUpdating(false);
    })();
    return () => { cancelled = true; };
  }, []);

  // Inputs of the selected line; refetched when the line changes and after a refresh.
  useEffect(() => {
    let cancelled = false;
    fetchQuotationInputs(lineFilter).then((byId) => {
      if (!cancelled) setInputs({ line: lineFilter, byId });
    });
    return () => { cancelled = true; };
  }, [lineFilter, inputsVersion]);

  // A quotation without a prediction (its policy has ended, or no model yet) keeps
  // null -> "—".
  const rows = useMemo(() => quotations.map((q) => {
    const p = predictions.get(`${q.line}-${q.id}`);
    // Display-only quote number: Fire and Motor ids overlap, so prefix the line (FQ- / MQ-).
    // Kept on the row so the all-fields search also matches e.g. "fq-1002".
    const quote_number = `${q.line === "Motor Car" ? "MQ" : "FQ"}-${q.id}`;
    const i = (q.line === inputs.line && inputs.byId.get(q.id)) || {};
    // The model inputs as shown (e.g. "7 yrs", "Yes"), kept on the row so the search matches them.
    const input_cells = (INPUT_COLUMNS[q.line] ?? []).map(([, show]) => show(i) ?? null);
    return {
      ...q, quote_number, survey_id: i.survey_id ?? null, input_cells,
      risk_level: p?.risk_level ?? null, claim_probability: p?.claim_probability ?? null,
    };
  }), [quotations, predictions, inputs]);

  // The bar's full height must equal the real total (t.quotation_count),
  // with "Converted" as a segment WITHIN it — not stacked on top of it.
  // Stacking converted_count + quotation_count (the raw total) double-
  // counts, since quotation_count already includes the converted ones;
  // stack converted_count + (total - converted) instead, so the two
  // segments sum exactly to the total.
  const trendData = useMemo(() => (stats?.trend ?? []).map((t) => ({
    label: t.label,
    converted_count: t.converted_count,
    not_converted_count: Math.max(0, t.quotation_count - t.converted_count),
  })), [stats]);

  // Table rows are scoped to the exact same range_start/range_end the
  // backend used for the KPI cards/pies/trend above (rolling window OR the
  // one selected month) — reuses the backend's own date math instead of
  // re-deriving "Past X Months" bounds in JS. Both are plain ISO
  // "YYYY-MM-DD" strings, so a lexicographic compare is a valid date
  // compare. A quotation with no date is excluded either way, same as the
  // backend's own SQL range filter excludes NULL quotation_date rows.
  const filtered = rows.filter((q) => {
    const matchRange = !!stats && !!q.quotation_date
      && q.quotation_date >= stats.range_start && q.quotation_date <= stats.range_end;
    const matchLine = q.line === lineFilter;
    // Low / Medium / High only match rows that have a prediction; "All" also
    // keeps the rows shown as "—".
    const matchRisk = riskFilter === "Risk Assessment: All" || q.risk_level === riskFilter;
    // Status: same "has a linked policy" definition the
    // "Converted Accounts" KPI card already uses
    // (q.is_converted comes straight from fetchAllQuotations() in
    // lib/quotations.js).
    const matchStatus = statusFilter === "Status: All"
      || (statusFilter === "Converted" && q.is_converted)
      || (statusFilter === "Not Yet Converted" && !q.is_converted);
    // Same all-fields search as Policy Holder Info (lib/search.js): matches what is
    // shown, e.g. the date as MM/DD/YYYY; empty fields never match "null".
    const matchSearch = rowMatchesSearch(q, search);
    return matchRange && matchLine && matchRisk && matchStatus && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const pageRows   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };

  const conversionRateLabel = stats ? `${Math.round(stats.conversion_rate)}%` : "—";

  // Average Claim Possibility: mean predicted probability over the quotations the
  // table currently lists (period/month + every filter) that have a prediction.
  const predictedRows = filtered.filter((q) => q.claim_probability !== null);
  const averageClaimPossibility = predictedRows.length
    ? predictedRows.reduce((sum, q) => sum + q.claim_probability, 0) / predictedRows.length
    : null;
  const averageCaption = `Based on ${predictedRows.length} quotation${predictedRows.length !== 1 ? "s" : ""} · ${lineFilter}`;
  const idColumns = ID_COLUMNS[lineFilter];
  const inputHeaders = INPUT_COLUMNS[lineFilter].map(([header]) => header);
  const columnCount = idColumns.length + inputHeaders.length + 3; // + Risk Assessment, Claim Possibility, View

  // Drives the "All time" replacement sub-label on the 3 KPI cards + both
  // pies — reflects whichever filter is actually active.
  const periodLabel = month
    ? `${MONTH_NAMES[month.getMonth()]} ${month.getFullYear()}`
    : period;

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
            <TrendChart data={trendData} />
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <MiniPie title="Fire & Property" data={stats?.fire_pie} sub={periodLabel} />
            <MiniPie title="Motor & Car"     data={stats?.motor_pie} sub={periodLabel} />
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
              <Dropdown label="Risk Assessment: All" options={["Risk Assessment: All", ...RISK_LEVELS]} value={riskFilter} onChange={handleFilterChange(setRisk)} />
              <Dropdown label="Motor Car"            options={LINES} value={lineFilter} onChange={handleFilterChange(setLine)} />
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
              {predictionsUpdating && <span className="text-xs text-violet-500">Updating predictions…</span>}
            </div>
            {quotationsError && <p className="text-xs text-red-600 mb-3">{quotationsError}</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-center">
                <thead>
                  <tr className="border-b border-gray-100">
                    {[...idColumns.map(([h]) => h), ...inputHeaders, "Risk Assessment", "Claim Possibility"].map(h => (
                      <th key={h} className="py-2 px-2 text-gray-500 font-semibold">{h}</th>
                    ))}
                    {/* Headers may wrap so the table fits a 1280 px screen; the View column is also pinned to
                        the right edge, so it stays visible if a narrower window makes the table scroll. */}
                    <th className="py-2 px-2 text-gray-500 font-semibold sticky right-0 bg-white border-l border-gray-100">
                      Geospatial Information
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {quotationsLoading && (
                    <tr><td colSpan={columnCount} className="py-6 text-gray-400 text-xs">Loading quotations…</td></tr>
                  )}
                  {!quotationsLoading && pageRows.map((r) => (
                    <tr key={`${r.line}-${r.id}`} className="group border-b border-gray-50 hover:bg-gray-50 transition">
                      {idColumns.map(([h, value]) => (
                        <td key={h} className="py-2.5 px-2 whitespace-nowrap">{value(r) ?? "—"}</td>
                      ))}
                      {r.input_cells.map((v, k) => (
                        <td key={inputHeaders[k]} className="py-2.5 px-2 whitespace-nowrap">{v ?? "—"}</td>
                      ))}
                      <td className="py-2.5 px-2"><RiskLevelCell value={r.risk_level} /></td>
                      <td className="py-2.5 px-2"><ClaimPossibilityCell value={r.claim_probability} /></td>
                      <td className="py-2.5 px-2 sticky right-0 bg-white group-hover:bg-gray-50 transition border-l border-gray-100">
                        <button onClick={() => setFloodModalQuotation(r)}
                          className="bg-black text-white text-[11px] px-3 py-1 rounded-lg hover:bg-gray-800 transition">View</button>
                      </td>
                    </tr>
                  ))}
                  {!quotationsLoading && pageRows.length === 0 && (
                    <tr><td colSpan={columnCount} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
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
            {/* Follows the table: same period/month and filters. */}
            <div className="bg-white rounded-2xl p-5 shadow-sm flex flex-col gap-1">
              <p className="text-gray-400 text-[10px]">{quotationsLoading ? "…" : averageCaption}</p>
              <div className="flex items-center gap-3">
                <p className="text-black font-black text-4xl leading-none">
                  {quotationsLoading ? "…" : formatPercent(averageClaimPossibility)}
                </p>
                <p className="text-gray-600 text-xs leading-snug">Average Claim<br />Possibility</p>
              </div>
            </div>
            <PolicyForecastCard forecast={forecast} error={forecastError} />
            <ModelAccuracyCard
              title="Model accuracy (Logistic Regression)"
              loading={models === null}
              rows={[
                { label: "Motor Car", model: models?.motor_lr, positives: "losses" },
                { label: "Fire & Property", model: models?.fire_lr, positives: "losses" },
              ]}
            />
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
