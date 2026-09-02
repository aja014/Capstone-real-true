import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import {
  StatCard, PolicyTable, MiniPie, fetchDistributionPolicies,
  getPeriodRange, filterRowsByRange, formatCurrencyPH, formatHumanDate, todayISO,
} from "./PolicyDistributionShared";
import { FullCalendarPicker } from "./DatePicker";

const API_BASE_URL = "http://127.0.0.1:8000";
const FIRE_COLORS = ["#a5b4fc", "#c4b5fd"];
const MOTOR_COLORS = ["#f87171", "#fca5a5"];

function toISO(date) {
  if (!date) return null;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function MTDView() {
  const [search, setSearch] = useState("");
  const [fromDate, setFromDate] = useState(null); // null => defaults to today
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refDate = toISO(fromDate) || todayISO();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [statsRes, allRows] = await Promise.all([
        axios.get(`${API_BASE_URL}/stats/policy-distribution`, { headers, params: { period: "mtd", date: refDate } }),
        fetchDistributionPolicies(),
      ]);
      setStats(statsRes.data);
      const { start, end } = getPeriodRange("mtd", refDate);
      setRows(filterRowsByRange(allRows, start, end));
    } catch {
      setError("Failed to load Policy Distribution data.");
    } finally {
      setLoading(false);
    }
  }, [refDate]);

  useEffect(() => { load(); }, [load]);

  const sub = `As of ${formatHumanDate(refDate)}`;
  const barData = (stats?.bar_chart ?? []).map((b) => ({ day: b.label, fire: b.fire_count, motor: b.motor_count }));
  const firePie = stats?.fire_pie ?? [];
  const motorPie = stats?.motor_pie ?? [];

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub={sub} value={loading ? "…" : String(stats?.total_policies ?? 0)} label="Total Policies Made" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.fire_count ?? 0)} label="Fire & Property Policies" />
        <StatCard sub={sub} value={loading ? "…" : String(stats?.motor_count ?? 0)} label="Motor & Car Policies" />
        <StatCard sub={sub} value={loading ? "…" : formatCurrencyPH(stats?.total_amount_due, false)} label="Total Amount Due" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
          <h2 className="font-bold text-black text-sm mb-1">
            Policy Type: Motor & Car vs. Fire & Property{" "}
            <span className="text-gray-400 font-normal">({sub})</span>
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={barData} barCategoryGap="15%" margin={{ left: -10 }}>
              <CartesianGrid vertical={false} stroke="#f3f4f6" />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false}
                label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 11 }} />
              <Bar dataKey="fire" name="Fire & Property" stackId="a" fill="#a5b4fc" />
              <Bar dataKey="motor" name="Motor & Car" stackId="a" fill="#f87171" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-1 justify-center">
            {[["#a5b4fc", "Fire & Property"], ["#f87171", "Motor & Car"]].map(([c, l]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm" style={{ background: c }} />
                <span className="text-[10px] text-gray-500">{l}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <MiniPie title="Fire & Property" data={firePie} colors={FIRE_COLORS} sub={sub} />
          <MiniPie title="Motor & Car" data={motorPie} colors={MOTOR_COLORS} sub={sub} />
        </div>
      </div>

      <PolicyTable
        search={search}
        setSearch={setSearch}
        data={rows}
        extraFilters={
          <div className="flex items-center gap-2 ml-auto">
            <FullCalendarPicker value={fromDate} onChange={setFromDate} />
            {fromDate && (
              <button
                type="button"
                onClick={() => setFromDate(null)}
                className="flex items-center cursor-pointer gap-1.5 bg-violet-50 border border-violet-200 text-violet-600 text-xs font-semibold px-3 py-1.5 rounded-xl hover:bg-violet-50 hover:border-violet-200 hover:text-violet-500 transition"
              >
                Reset to Today
              </button>
            )}
          </div>
        }
      />
    </div>
  );
}
