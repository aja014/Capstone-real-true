import { useState, useEffect, useCallback } from "react";
import { sharedGet } from "../lib/sharedGet";
import {
  StatCard, PolicyTable, fetchDistributionPolicies,
  getPeriodRange, filterRowsByRange, formatCurrencyPH, formatHumanDate, todayISO,
} from "./PolicyDistributionShared";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function DailyView() {
  const [search, setSearch] = useState("");
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const date = todayISO();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [statsRes, allRows] = await Promise.all([
        sharedGet(`${API_BASE_URL}/stats/policy-distribution`, { headers, params: { period: "daily", date } }),
        fetchDistributionPolicies(),
      ]);
      setStats(statsRes.data);
      const { start, end } = getPeriodRange("daily", date);
      setRows(filterRowsByRange(allRows, start, end));
    } catch {
      setError("Failed to load Policy Distribution data.");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const sub = `As of ${formatHumanDate(date)}`;

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub={sub} value={loading ? "…" : String(stats?.total_policies ?? 0)} label="Total Policies Today" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.fire_count ?? 0)} label="Fire & Property Policies" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.motor_count ?? 0)} label="Motor & Car Policies" />
        <StatCard sub={sub} value={loading ? "…" : formatCurrencyPH(stats?.total_amount_due, false)} label="Total Amount Due" />
      </div>

      <PolicyTable search={search} setSearch={setSearch} data={rows} />
    </div>
  );
}
