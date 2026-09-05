import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { StatCard, PolicyTable, formatHumanDate, todayISO } from "./PolicyDistributionShared";
import { mapRenewalRow, RenewalRateCard, RENEWAL_STATUS_OPTIONS, ExpiryDateFilter, filterRowsByExpiryDate } from "./RenewalRatioShared";

const API_BASE_URL = "http://127.0.0.1:8000";

export default function RenewalDailyView() {
  const [search, setSearch] = useState("");
  const [expiryFilterDate, setExpiryFilterDate] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const date = todayISO();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.get(`${API_BASE_URL}/stats/renewal-ratio`, { headers, params: { period: "daily", date } });
      setStats(res.data);
    } catch {
      setError("Failed to load Renewal Ratio data.");
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const sub = `As of ${formatHumanDate(date)}`;
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
