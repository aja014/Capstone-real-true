import { useState, useEffect, useCallback } from "react";
import { sharedGet } from "../lib/sharedGet";
import { StatCard, PolicyTable, formatHumanDate, todayISO } from "./PolicyDistributionShared";
import { mapRenewalRow, RenewalRateCard, RENEWAL_STATUS_OPTIONS, ExpiryDateFilter, filterRowsByExpiryDate } from "./RenewalRatioShared";

import { API_BASE_URL } from "../api/config";

export default function RenewalDailyView({ ytdRenewalRate }) {
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
      const res = await sharedGet(`${API_BASE_URL}/stats/renewal-ratio`, { headers, params: { period: "daily", date } });
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
  // Renewal Rate card always shows YTD, regardless of this view's own period.
  const rate = ytdRenewalRate != null ? `${Number(ytdRenewalRate).toFixed(2)}%` : "…";

  return (
    <div className="flex flex-col gap-4 flex-1">
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub={sub} value={loading ? "…" : String(stats?.expiring_count ?? 0)} label="Expiring Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.renewed_count ?? 0)} label="Renewed Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.lost_count ?? 0)} label="Lost Policy" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.pending_count ?? 0)} label="Pending" />
      </div>

      <div className="flex gap-4 flex-1">
        <PolicyTable
          data={rows}
          statusOptions={RENEWAL_STATUS_OPTIONS}
          extraFilters={<ExpiryDateFilter value={expiryFilterDate} onChange={setExpiryFilterDate} />}
        />
        <RenewalRateCard rate={rate} />
      </div>
    </div>
  );
}
