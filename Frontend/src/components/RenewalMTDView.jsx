import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { StatCard, PolicyTable, MiniPie, formatHumanDate, todayISO } from "./PolicyDistributionShared";
import { mapRenewalRow, RenewalRateCard, RENEWAL_STATUS_OPTIONS, RENEWAL_PIE_COLORS, ExpiryDateFilter, filterRowsByExpiryDate } from "./RenewalRatioShared";

const API_BASE_URL = "http://127.0.0.1:8000";

function legendLabel(v) {
  if (v === "renewed") return "Renewed Policies";
  if (v === "lost") return "Lost Policies";
  return "Pending";
}

export default function RenewalMTDView() {
  const [search, setSearch] = useState("");
  const [expiryFilterDate, setExpiryFilterDate] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // "today" is fixed, never user-editable — MTD always shows the WHOLE
  // current month (including future-dated expiries), and Lost/Pending
  // status is always evaluated against the real current date. See
  // RenewalRatioShared / stats.py's _expiry_range_for_period: deliberately
  // NOT the Distribution FullCalendarPicker cutoff-at-picked-date pattern.
  const date = todayISO();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.get(`${API_BASE_URL}/stats/renewal-ratio`, { headers, params: { period: "mtd", date } });
      setStats(res.data);
    } catch {
      setError("Failed to load Renewal Ratio data.");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const sub = `As of ${formatHumanDate(date)}`;
  const barData = (stats?.bar_chart ?? []).map((b) => ({
    day: b.label, renewed: b.renewed_count, lost: b.lost_count, pending: b.pending_count,
  }));
  const firePie = stats?.fire_pie ?? [];
  const motorPie = stats?.motor_pie ?? [];
  const rows = filterRowsByExpiryDate((stats?.policies ?? []).map(mapRenewalRow), expiryFilterDate);
  const rate = stats ? `${Number(stats.renewal_rate).toFixed(2)}%` : "…";

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
          extraFilters={<ExpiryDateFilter value={expiryFilterDate} onChange={setExpiryFilterDate} />}
        />
        <RenewalRateCard rate={loading ? "…" : rate} sub={sub} />
      </div>
    </div>
  );
}
