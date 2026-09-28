import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LabelList,
} from "recharts";
import { Search } from "lucide-react";
import Sidebar from "../components/sidebar";
import { MonthYearPicker } from "../components/DatePicker";
import { Dropdown, StatCard, MiniPie, formatCurrencyPH, formatDateSlash } from "../components/PolicyDistributionShared";
import { InvestigationResultCell, FraudWarningCell } from "../components/ClaimsShared";
import { fetchAllClaims, investigationFilterValue, NOT_YET_INVESTIGATED } from "../lib/claims";
import { fetchModels, waitForModelRefresh } from "../lib/ml";
import { ModelAccuracyCard } from "../components/ModelShared";

const API_BASE_URL = "http://127.0.0.1:8000";
const PAGE_SIZE = 8;
const PERIOD_TO_MONTHS = { "Past 6 Months": 6, "Past 3 Months": 3, "Past 12 Months": 12 };
const PIE_COLORS = ["#6366f1", "#f59e0b", "#ef4444", "#d1d5db"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const FINAL_STATUS_OPTIONS = [
  "No Docs. Submitted", "Waiting for Evaluation", "Waiting for LOA",
  "Waiting for Billing", "Waiting for Claim Check", "Closed Claim",
  "Denied Claim", "CNC Only", "Not Push Through", "With Lacking Docs",
  "Hold per Client",
];
const INVESTIGATION_OPTIONS = [
  "Investigation Result: All", "Legitimate", "Suspected Fraud", "Confirmed Fraud", NOT_YET_INVESTIGATED,
];

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Claims Module. Cards, trend chart, investigation pie and fraud rate all come
// from GET /stats/claims and share one basis: claims FILED (Date Reported) in
// the selected Past 3/6/12 Months window. The table below lists every claim
// (both lines, joined in lib/claims.js) with its own filters -- it is NOT
// limited by the period dropdown. "Fraud Warning" is the Naive Bayes prediction
// (uninvestigated Paid Claims only); "Claim Investigation Result" is the real human label.
export default function Claims() {
  const [period, setPeriod] = useState("Past 6 Months");
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState(null);

  const [claims, setClaims] = useState([]);
  const [claimsLoading, setClaimsLoading] = useState(true);
  const [claimsError, setClaimsError] = useState(null);

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [month, setMonth] = useState(null);
  const [lineFilter, setLine] = useState("Policy Line: All");
  const [statusFilter, setStatus] = useState("Final Status: All");
  const [investigationFilter, setInvestigation] = useState("Investigation Result: All");
  const [models, setModels] = useState(null); // GET /ml/models summaries; null while loading
  const [predictionsUpdating, setPredictionsUpdating] = useState(false);

  const fetchStats = useCallback(async (months) => {
    setStatsError(null);
    try {
      const res = await axios.get(`${API_BASE_URL}/stats/claims`, { params: { months }, headers: authHeaders() });
      setStats(res.data);
    } catch {
      setStatsError("Failed to load claims stats.");
    }
  }, []);

  useEffect(() => { fetchStats(PERIOD_TO_MONTHS[period] ?? 6); }, [period, fetchStats]);

  const loadClaims = useCallback(async () => {
    setClaimsLoading(true);
    setClaimsError(null);
    try {
      const { motor, fire } = await fetchAllClaims();
      // Newest filing first.
      setClaims([...motor, ...fire].sort((a, b) => (b.date_reported || "").localeCompare(a.date_reported || "")));
    } catch {
      setClaimsError("Failed to load claims.");
    } finally {
      setClaimsLoading(false);
    }
  }, []);

  // Claims (with their Fraud Warning) + model scores. If the page is opened while the
  // background retrain (started by an upload on Policy Holder Information) is still
  // running, wait for it and then reload the claims and scores.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      loadClaims();
      const { byName, refresh } = await fetchModels();
      if (cancelled) return;
      setModels(byName);
      if (!refresh?.running) return;
      setPredictionsUpdating(true);
      await waitForModelRefresh({ isCancelled: () => cancelled });
      if (cancelled) return;
      setPredictionsUpdating(false);
      loadClaims();
      setModels((await fetchModels()).byName);
    })();
    return () => { cancelled = true; };
  }, [loadClaims]);

  const periodLabel = stats?.period_label ?? period;

  // Stacked Motor/Fire bars sum to the real monthly total; the line is the
  // human "Investigated as Fraud" label (Suspected + Confirmed), not a prediction.
  const trendData = (stats?.trend ?? []).map((t) => ({
    label: t.label,
    motor_count: t.motor_count,
    fire_count: t.fire_count,
    fraud_labelled_count: t.fraud_labelled_count,
  }));

  const filtered = claims.filter((r) => {
    let matchMonth = true;
    if (month) {
      const [y, m] = (r.date_reported || "").split("-").map(Number);
      matchMonth = y === month.getFullYear() && m === month.getMonth() + 1;
    }
    const matchLine = lineFilter === "Policy Line: All" || r.line === lineFilter;
    const matchStatus = statusFilter === "Final Status: All" || r.final_status === statusFilter;
    const matchInvestigation = investigationFilter === "Investigation Result: All"
      || investigationFilterValue(r) === investigationFilter;
    const searchText = search.toLowerCase();
    const matchSearch = searchText === "" || [r.policy_no, r.client_name, r.assured, r.accuterm_claim_no]
      .some((v) => String(v ?? "").toLowerCase().includes(searchText));
    return matchMonth && matchLine && matchStatus && matchInvestigation && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };
  const anyFilter = month || search || lineFilter !== "Policy Line: All"
    || statusFilter !== "Final Status: All" || investigationFilter !== "Investigation Result: All";

  const fraudRateLabel = !stats ? "…" : stats.fraud_rate === null ? "—" : `${stats.fraud_rate.toFixed(1)}%`;

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0"><Sidebar activeItem="Claims" /></div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {statsError && <p className="text-xs text-red-600 bg-white/70 rounded-lg px-3 py-2">{statsError}</p>}

        {/* All five cards: claims filed (Date Reported) in the selected period.
            Open + Closed + Other Finished = Total Claims. */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard sub={`Filed ${periodLabel}`} value={stats ? stats.total_claims : "…"} label="Total Claims" />
          <StatCard sub={`Filed ${periodLabel}`} value={stats ? stats.open_claims : "…"} label="Open Claims" />
          <StatCard sub={`Filed ${periodLabel}`} value={stats ? stats.closed_claims : "…"} label="Closed Claims" />
          <StatCard sub={`Filed ${periodLabel}`} value={stats ? stats.other_claims : "…"} label="Other Finished"
            note="Denied, CNC Only, Not Push Through" />
          <StatCard sub={`Filed ${periodLabel}`}
            value={stats ? formatCurrencyPH(stats.total_net_liability, false) : "…"} label="Total Net Liability" />
        </div>

        <div className="flex gap-4">
          <div className="flex-1 bg-white rounded-2xl p-5 shadow-sm flex flex-col gap-3 min-w-0">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-black text-sm">
                Filed Claims per Month <span className="text-gray-400 font-normal">(by Date Reported)</span>
              </h2>
              <Dropdown label="Past 6 Months" options={Object.keys(PERIOD_TO_MONTHS)} value={period} onChange={setPeriod} />
            </div>
            {/* Grows with the right-hand column of cards (min 270px) instead of leaving a gap. */}
            <div className="flex-1 min-h-[270px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={trendData} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false}
                  label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {/* Explicit LabelList per segment: a stacked Bar's built-in label shows the
                    running total (Motor + Fire) on the upper segment, not its own count. */}
                <Bar dataKey="motor_count" name="Motor & Car" stackId="a" fill="#6366f1">
                  <LabelList dataKey="motor_count" position="center" formatter={(v) => v || ""}
                    style={{ fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                </Bar>
                <Bar dataKey="fire_count" name="Fire & Property" stackId="a" fill="#a5b4fc" radius={[4, 4, 0, 0]}>
                  <LabelList dataKey="fire_count" position="center" formatter={(v) => v || ""}
                    style={{ fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                </Bar>
                <Line dataKey="fraud_labelled_count" name="Investigated as Fraud (human label)"
                  stroke="#ef4444" strokeWidth={2} dot={{ r: 4, fill: "#ef4444" }} />
              </ComposedChart>
            </ResponsiveContainer>
            </div>
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <MiniPie
              title="Claim Investigation Result"
              data={stats?.investigation_pie ?? []}
              colors={PIE_COLORS}
              sub={`Filed ${periodLabel}`}
              note={stats ? `CNC Issuance rows are excluded (${stats.cnc_excluded} in this period).` : null}
            />
            <div className="bg-white rounded-2xl p-4 shadow-sm">
              <p className="text-black font-bold text-sm">Fraud Rate</p>
              <p className="text-gray-400 text-[10px]">Filed {periodLabel} · investigated claims, CNC excluded</p>
              <p className="text-black font-black text-4xl mt-2">{fraudRateLabel}</p>
              <p className="text-gray-400 text-[10px] mt-1">(Suspected + Confirmed Fraud) ÷ investigated × 100</p>
            </div>
            <ModelAccuracyCard
              title="Fraud model accuracy (Naive Bayes)"
              loading={models === null}
              rows={[{ label: "Motor Car and Fire & Property", model: models?.fraud_nb, positives: "fraud" }]}
            />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <p className="text-gray-400 text-[10px] mb-2">All claims, both lines — not limited by the period above.</p>
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
            <Dropdown label="Policy Line: All" options={["Policy Line: All", "Motor Car", "Fire & Property"]}
              value={lineFilter} onChange={handleFilterChange(setLine)} />
            <Dropdown label="Final Status: All" options={["Final Status: All", ...FINAL_STATUS_OPTIONS]}
              value={statusFilter} onChange={handleFilterChange(setStatus)} />
            <Dropdown label="Investigation Result: All" options={INVESTIGATION_OPTIONS}
              value={investigationFilter} onChange={handleFilterChange(setInvestigation)} />
            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
              <Search className="w-3.5 h-3.5 text-gray-400" />
              <input className="text-xs outline-none text-gray-600 w-44" placeholder="Search policy, client, claim no."
                value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
            </div>
            {predictionsUpdating && <span className="text-xs text-violet-500">Updating fraud predictions…</span>}
            {anyFilter && (
              <span className="text-xs text-gray-400">
                {filtered.length} result{filtered.length !== 1 ? "s" : ""}
                {month ? ` · reported in ${MONTH_NAMES[month.getMonth()]} ${month.getFullYear()}` : ""}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            {claimsLoading
              ? <p className="text-center py-8 text-gray-400 text-xs">Loading claims...</p>
              : claimsError
              ? <p className="text-center py-8 text-red-400 text-xs">{claimsError}</p>
              : (
                <table className="min-w-max w-full text-xs text-center">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Claim ID", "Accuterm Claim No.", "Policy No.", "Client Name", "Policy Line", "Date of Loss",
                        "Date Reported", "Nature of Loss", "Claim Type", "Net Liability", "Final Status",
                        "Claim Investigation Result", "Fraud Warning"].map((h) => (
                        <th key={h} className="py-2 px-2 text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((r) => (
                      <tr key={`${r.line}-${r.id}`} className="border-b border-gray-50 hover:bg-gray-50 transition">
                        <td className="py-2.5 px-2">{r.id}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.accuterm_claim_no ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.policy_no ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap text-left">{r.client_name ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.line}</td>
                        <td className="py-2.5 px-2">{formatDateSlash(r.date_of_loss)}</td>
                        <td className="py-2.5 px-2">{formatDateSlash(r.date_reported)}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.nature_of_loss ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.claim_type ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{formatCurrencyPH(r.net_liability)}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap">{r.final_status ?? "—"}</td>
                        <td className="py-2.5 px-2 whitespace-nowrap"><InvestigationResultCell value={r.investigation_display} /></td>
                        <td className="py-2.5 px-2 whitespace-nowrap"><FraudWarningCell value={r.fraud_warning} flagged={r.fraud_flag} /></td>
                      </tr>
                    ))}
                    {pageRows.length === 0 && (
                      <tr><td colSpan={13} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                    )}
                  </tbody>
                </table>
              )}
          </div>
          <div className="flex justify-end items-center gap-2 mt-3 text-xs text-gray-500">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
            <span>{safePage} / {totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
          </div>
        </div>
      </div>
    </div>
  );
}
