import { useState, useEffect, useCallback } from "react";
import { sharedGet } from "../lib/sharedGet";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { StatCard, PolicyTable, MiniPie, formatMonthYear, dateToISO, todayISO } from "./PolicyDistributionShared";
import { mapRenewalRow, RenewalRateCard, RENEWAL_STATUS_OPTIONS, RENEWAL_PIE_COLORS, MonthExpiryFilterMTD } from "./RenewalRatioShared";

const API_BASE_URL = "http://127.0.0.1:8000";

function legendLabel(v) {
  if (v === "renewed") return "Renewed Policies";
  if (v === "lost") return "Lost Policies";
  return "Pending";
}

export default function RenewalMTDView({ ytdRenewalRate }) {
  const [search, setSearch] = useState("");
  const [month, setMonth] = useState(null); // null => the real current month
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // No month picked -> the real current month (today), unchanged default
  // behavior. A picked month re-scopes the whole view -- stat cards, bar
  // chart, pies, AND table -- via the `date` param below. Lost/Pending
  // status itself is always judged against the real current date
  // server-side (stats.py's get_renewal_ratio), regardless of which
  // month's window is being browsed here.
  const date = month ? dateToISO(month) : todayISO();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await sharedGet(`${API_BASE_URL}/stats/renewal-ratio`, { headers, params: { period: "mtd", date } });
      setStats(res.data);
    } catch {
      setError("Failed to load Renewal Ratio data.");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const sub = `As of ${formatMonthYear(date)}`;
  const barData = (stats?.bar_chart ?? []).map((b) => ({
    day: b.label, renewed: b.renewed_count, lost: b.lost_count, pending: b.pending_count,
  }));
  const firePie = stats?.fire_pie ?? [];
  const motorPie = stats?.motor_pie ?? [];
  const rows = (stats?.policies ?? []).map(mapRenewalRow);
  // Renewal Rate card always shows YTD, regardless of this view's own period.
  const rate = ytdRenewalRate != null ? `${Number(ytdRenewalRate).toFixed(2)}%` : "…";

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub={sub} value={loading ? "…" : String(stats?.expiring_count ?? 0)} label="Expiring Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.renewed_count ?? 0)} label="Renewed Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.lost_count ?? 0)} label="Lost Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.pending_count ?? 0)} label="Pending" />
      </div>

      <div className="flex gap-4">
        <div className="flex-1 bg-white rounded-2xl p-5 shadow-sm min-w-0">
          <h2 className="font-bold text-black text-sm mb-3">
            MTD Policy Retention: Renewed vs. Lost{" "}
            <span className="text-gray-400 font-normal">(Stacked by Day, {sub})</span>
          </h2>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={barData} barCategoryGap="30%">
              <CartesianGrid vertical={false} stroke="#f3f4f6" />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false}
                label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} formatter={legendLabel} />
              <Bar dataKey="renewed" name="renewed" stackId="a" fill="#6366f1" />
              <Bar dataKey="lost" name="lost" stackId="a" fill="#f87171" />
              <Bar dataKey="pending" name="pending" stackId="a" fill="#d1d5db" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-3 w-64 flex-shrink-0">
          <MiniPie title="Fire & Property" data={firePie} colors={RENEWAL_PIE_COLORS} sub={sub} />
          <MiniPie title="Motor & Car" data={motorPie} colors={RENEWAL_PIE_COLORS} sub={sub} />
        </div>
      </div>

      <div className="flex gap-4">
        <PolicyTable
          search={search}
          setSearch={setSearch}
          data={rows}
          statusOptions={RENEWAL_STATUS_OPTIONS}
          premiumLabel="Premium"
          extraFilters={<MonthExpiryFilterMTD value={month} onChange={setMonth} />}
        />
        <RenewalRateCard rate={rate} />
      </div>
    </div>
  );
}
